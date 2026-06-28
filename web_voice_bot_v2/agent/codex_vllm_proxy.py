"""
Codex → vLLM 适配代理 (Responses ↔ Chat Completions)

为什么需要它 (都是实测结论):
  - Codex 0.135 只说 OpenAI Responses API (已删 wire_api="chat")。
  - 本地 vLLM (dev 版) 的 /v1/responses 对 Codex 的请求形态不兼容:
      * 不认 `developer` 角色 → "Unexpected message role"
      * system 必须在最前 → "System message must be at the beginning"
  - 更关键: 这个 Qwen3.5-W4A16 模型在 /v1/responses 上无视 enable_thinking,
    把整个 token 预算耗在 "Thinking Process..." 上, 真正回答被 max_output_tokens
    截断 → Codex 拿到空消息。
  - 但同一模型在 /v1/chat/completions + enable_thinking=false 上输出干净简短
    (现有 llm_handler 已验证)。

所以本代理:
  1. 接收 Codex 的 Responses 请求;
  2. 归一化 input → chat messages (system 合并前置, 丢 reasoning/工具项);
  3. 打 vLLM 的 /v1/chat/completions (enable_thinking=false, 非流式) 拿干净回答;
  4. 把回答**合成**成 Codex 能解析的 Responses SSE 事件序列 (或 JSON) 返回。

启动:  python agent/codex_vllm_proxy.py
环境变量:
  PROXY_PORT            监听端口 (默认 8210)
  VLLM_BASE_URL         vLLM base (默认 http://localhost:8102/v1)
  VLLM_MODEL            强制 model (默认用 Codex 传来的)
  PROXY_TEMPERATURE     采样温度 (默认 0.7)
  PROXY_MAX_TOKENS      回答上限 floor (默认 512)
"""

import os
import re
import time
import json
import logging
import threading
import datetime

import httpx
from flask import Flask, request, Response

logger = logging.getLogger(__name__)

VLLM_BASE = os.environ.get("VLLM_BASE_URL", "http://localhost:8102/v1").rstrip("/")
MODEL_OVERRIDE = os.environ.get("VLLM_MODEL", "").strip()
TEMPERATURE = float(os.environ.get("PROXY_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.environ.get("PROXY_MAX_TOKENS", "512"))
PORT = int(os.environ.get("PROXY_PORT", "8210"))

# 系统提示模式:
#   replace = 丢弃 Codex 的 ~26KB 编程 agent 指令,换成我们简短的语音人设
#             (大幅降低 vLLM 预填延迟:7000 token → ~100 token)
#   merge   = 保留 Codex 指令(原始行为,慢)
SYSTEM_MODE = os.environ.get("PROXY_SYSTEM_MODE", "replace")

_BUILTIN_PERSONA = (
    "你是一个运行在设备上的中文语音助手。回答必须简短口语化(1-2句),"
    "不要用Markdown,不要输出思考过程、emoji、URL或括号注释。"
    "你能记住本次对话里用户说过的事并自然延续。"
)


def _load_persona() -> str:
    # 优先用 PROXY_SYSTEM_PROMPT;否则读 AGENTS.md;再否则用内置
    p = os.environ.get("PROXY_SYSTEM_PROMPT")
    if p:
        return p
    agents_file = os.environ.get(
        "PROXY_AGENTS_FILE",
        os.path.join(os.path.dirname(__file__), "..", ".codex_home", "workspace", "AGENTS.md"),
    )
    try:
        with open(agents_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return _BUILTIN_PERSONA


PERSONA = _load_persona()

# 长期记忆 + context 限长
MEMORY_ENABLED = os.environ.get("PROXY_MEMORY", "1") == "1"
MEMORY_DIR = os.environ.get(
    "MEMORY_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "memory"))
MEMORY_TOPK = int(os.environ.get("MEMORY_TOPK", "3"))
# 发给 vLLM 的对话消息上限(user+assistant 条数),限制预填延迟随对话增长
MAX_TURN_MSGS = int(os.environ.get("PROXY_MAX_TURN_MSGS", "12"))

_memory = None
if MEMORY_ENABLED:
    try:
        from memory_store import VectorMemory
    except ImportError:
        from agent.memory_store import VectorMemory
    _memory = VectorMemory(os.path.abspath(MEMORY_DIR))

_client = httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0))
app = Flask(__name__)


# ----------------------------------------------------------------------------
# 文本清洗:去掉 <think> 块和 "Thinking Process" 残留 (TTS 友好)
# ----------------------------------------------------------------------------
def strip_thinking(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    # 若模型仍以 "Thinking Process" 开头, 尽量截取其后的中文回答
    if "Thinking Process" in text or "思考过程" in text:
        # 取最后一段非空文本作为回答
        paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if paras:
            text = paras[-1]
    return text.strip()


# ----------------------------------------------------------------------------
# 请求归一化:Codex Responses input[] → chat messages[]
# ----------------------------------------------------------------------------
def _item_text(item: dict) -> str:
    parts = []
    for c in item.get("content", []) or []:
        if isinstance(c, dict) and "text" in c:
            parts.append(c.get("text", ""))
        elif isinstance(c, str):
            parts.append(c)
    return "".join(parts)


def to_chat_messages(body: dict):
    """返回 (messages, tools)。tools 来自 Codex,直接透传给 vLLM。"""
    system_texts = []
    if SYSTEM_MODE == "merge" and body.get("instructions"):
        system_texts.append(str(body["instructions"]))

    convo = []
    tool_results = []  # function_call_output 类型的 item,稍后转成 tool role

    for it in body.get("input", []) or []:
        if not isinstance(it, dict):
            continue
        itype = it.get("type", "message")

        if itype == "message":
            role = it.get("role")
            text = _item_text(it)
            if role in ("system", "developer"):
                if SYSTEM_MODE == "merge":
                    system_texts.append(text)
                # replace 模式:丢弃 Codex 注入的所有 system/developer 内容(含 26KB 指令)
            elif role in ("user", "assistant"):
                convo.append({"role": role, "content": text})

        elif itype == "function_call_output":
            # Codex 传来的工具调用结果,需转成 vLLM 的 tool 消息
            tool_results.append(it)

    messages = []
    if SYSTEM_MODE == "replace":
        messages.append({"role": "system", "content": PERSONA})
    else:
        merged = "\n\n".join(t for t in system_texts if t and t.strip())
        if merged:
            messages.append({"role": "system", "content": merged})
    messages.extend(convo)

    # 把 tool_results 插到对话末尾(在最后一个 assistant 消息后,如果有 function_call 的话)
    for tr in tool_results:
        call_id = tr.get("call_id", "unknown")
        output = tr.get("output", "")
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": output
        })

    # 提取 tools(Codex 传来的,需转换成 OpenAI 格式再给 vLLM)
    raw_tools = body.get("tools") or []
    tools = []
    for t in raw_tools:
        if not isinstance(t, dict):
            continue
        # Codex 格式:{type:"function", name, description, parameters, ...}
        # OpenAI 格式:{type:"function", function:{name, description, parameters}}
        if "function" in t:
            # 已经是 OpenAI 格式
            tools.append(t)
        elif t.get("type") == "function" and "name" in t:
            # Codex 扁平格式,转成嵌套
            tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}})
                }
            })

    return messages, tools


# ----------------------------------------------------------------------------
# 调 vLLM chat/completions 拿回答(可能带工具调用)
# ----------------------------------------------------------------------------
def call_vllm_chat(model: str, messages, tools, max_tokens: int, temperature: float):
    """返回 (answer: str | None, tool_calls: list | None)"""
    req = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if tools:
        req["tools"] = tools
        req["tool_choice"] = "auto"
        # DEBUG: 打印传给 vLLM 的工具定义（打印前2个：weather和web_search）
        if len(tools) > 0 and logger.level <= 20:  # INFO level
            logger.info("DEBUG: 传给 vLLM 的工具示例 [0] weather: %s", json.dumps(tools[0], ensure_ascii=False, indent=2))
            if len(tools) > 1:
                logger.info("DEBUG: 传给 vLLM 的工具示例 [1] web_search: %s", json.dumps(tools[1], ensure_ascii=False, indent=2))

    sys_chars = sum(len(m.get("content", "")) for m in messages if m.get("role") == "system")
    _t = time.time()
    r = _client.post(f"{VLLM_BASE}/chat/completions", json=req)
    if r.status_code != 200:
        logger.error("vLLM error %d: %s", r.status_code, r.text[:500])
    r.raise_for_status()
    logger.info("upstream vLLM call: %.2fs (system_chars=%d)", time.time() - _t, sys_chars)

    msg = r.json()["choices"][0]["message"]
    content = msg.get("content")
    tool_calls = msg.get("tool_calls")

    # DEBUG: 打印 vLLM 返回的原始数据
    if tool_calls:
        logger.info("DEBUG: vLLM 返回了 tool_calls: %s", json.dumps(tool_calls, ensure_ascii=False))

    answer = strip_thinking(content) if content else None
    return answer, tool_calls


# ----------------------------------------------------------------------------
# 把回答合成 Codex 能解析的 Responses 结果
# ----------------------------------------------------------------------------
def _rid():
    return "resp_" + os.urandom(8).hex()


def _mid():
    return "msg_" + os.urandom(8).hex()


def _base_response(rid: str, model: str, max_out: int, status: str, output):
    return {
        "id": rid, "created_at": int(time.time()),
        "incomplete_details": None, "instructions": None, "metadata": None,
        "model": model, "object": "response", "output": output,
        "parallel_tool_calls": True, "temperature": TEMPERATURE,
        "tool_choice": "none", "tools": [], "top_p": 1.0,
        "background": False, "max_output_tokens": max_out, "reasoning": None,
        "status": status, "text": None, "usage": None,
    }


def _final_item(mid: str, answer: str):
    return {
        "id": mid,
        "content": [{"annotations": [], "text": answer, "type": "output_text", "logprobs": None}],
        "role": "assistant", "status": "completed", "type": "message",
    }


def sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def synth_stream(answer: str, model: str, max_out: int):
    rid, mid, iid = _rid(), _mid(), os.urandom(8).hex()
    seq = {"n": 0}

    def nx():
        seq["n"] += 1
        return seq["n"]

    yield sse("response.created", {
        "response": _base_response(rid, model, max_out, "in_progress", []),
        "sequence_number": nx(), "type": "response.created"})

    item_stub = {"id": iid, "content": [], "role": "assistant",
                 "status": "in_progress", "type": "message"}
    yield sse("response.output_item.added", {
        "item": item_stub, "output_index": 0,
        "sequence_number": nx(), "type": "response.output_item.added"})

    yield sse("response.content_part.added", {
        "content_index": 0, "item_id": iid, "output_index": 0,
        "part": {"annotations": [], "text": "", "type": "output_text", "logprobs": []},
        "sequence_number": nx(), "type": "response.content_part.added"})

    yield sse("response.output_text.delta", {
        "content_index": 0, "delta": answer, "item_id": iid, "logprobs": [],
        "output_index": 0, "sequence_number": nx(), "type": "response.output_text.delta"})

    yield sse("response.output_text.done", {
        "content_index": 0, "item_id": iid, "logprobs": [], "output_index": 0,
        "sequence_number": nx(), "text": answer, "type": "response.output_text.done"})

    yield sse("response.content_part.done", {
        "content_index": 0, "item_id": iid, "output_index": 0,
        "part": {"annotations": [], "text": answer, "type": "output_text", "logprobs": None},
        "sequence_number": nx(), "type": "response.content_part.done"})

    final = _final_item(mid, answer)
    yield sse("response.output_item.done", {
        "item": final, "output_index": 0,
        "sequence_number": nx(), "type": "response.output_item.done"})

    yield sse("response.completed", {
        "response": _base_response(rid, model, max_out, "completed", [final]),
        "sequence_number": nx(), "type": "response.completed"})


# ----------------------------------------------------------------------------
# 长期记忆注入 + context 限长
# ----------------------------------------------------------------------------
def apply_memory_and_cap(messages):
    """限制最近对话条数(限延迟) + 注入与当前问题相关的长期记忆。返回 (messages, last_user)。"""
    sys_msgs = [m for m in messages if m["role"] == "system"]
    convo = [m for m in messages if m["role"] != "system"]

    # 最近 N 条对话(限制 vLLM 预填延迟随对话增长)
    capped = convo[-MAX_TURN_MSGS:] if MAX_TURN_MSGS > 0 else convo

    last_user = ""
    for m in reversed(convo):
        if m["role"] == "user":
            last_user = m["content"]
            break

    # 检索相关长期记忆,拼到 system 提示
    sys_text = sys_msgs[0]["content"] if sys_msgs else PERSONA
    if _memory is not None and last_user:
        try:
            mems = _memory.recall(last_user, k=MEMORY_TOPK)
            if mems:
                sys_text += "\n\n[你记得的相关信息]\n" + "\n".join(f"- {m}" for m in mems)
                logger.info("recalled %d memory item(s)", len(mems))
        except Exception as e:
            logger.warning("memory recall failed: %s", e)

    return [{"role": "system", "content": sys_text}] + capped, last_user


def store_memory(last_user: str, answer: str):
    if _memory is None or not last_user:
        return
    try:
        _memory.add(f"用户说:{last_user} | 助手答:{answer}")
    except Exception as e:
        logger.warning("memory store failed: %s", e)


# ----------------------------------------------------------------------------
# 内置系统工具 (在代理侧执行,不需要 Codex sandbox 权限)
# ----------------------------------------------------------------------------
def _year_to_chinese(year: int) -> str:
    """将年份转换为中文数字，避免模型误读 2026 为"一九二六" """
    digits = {'0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
              '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'}
    return ''.join(digits[d] for d in str(year))

def execute_mcp_tool(name: str, arguments: dict) -> str:
    """执行 MCP 工具（通过 npx 调用 MCP 服务器）"""
    import subprocess

    if name == "weather":
        location = arguments.get("location", "北京")
        try:
            # 调用 mcp-server-weather
            # 注意：MCP 服务器使用 stdio 协议，需要发送 JSON-RPC 请求
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_forecast",
                    "arguments": {"city": location}
                }
            }

            proc = subprocess.run(
                ["npx", "-y", "mcp-server-weather"],
                input=json.dumps(mcp_request),
                capture_output=True,
                text=True,
                timeout=10
            )

            if proc.returncode == 0 and proc.stdout:
                # 解析 MCP 服务器返回
                lines = proc.stdout.strip().split('\n')
                for line in lines:
                    try:
                        response = json.loads(line)
                        if response.get("result"):
                            return f"{location}的天气：{response['result']}"
                    except:
                        continue

            # 如果 MCP 调用失败，返回简单格式
            logger.warning(f"MCP weather tool failed: {proc.stderr[:200]}")
            return f"抱歉，暂时无法查询{location}的天气信息。"

        except Exception as e:
            logger.error(f"MCP weather execution error: {e}")
            return f"抱歉，查询{location}天气时出错了。"

    elif name == "web_search":
        query = arguments.get("query", "")
        try:
            # 调用 mcp-fetch-server 通过 SearxNG 搜索
            # 简化实现：直接调用 SearxNG API
            import httpx

            searxng_url = "http://searxng:8080/search"
            params = {"q": query, "format": "json"}

            response = httpx.get(searxng_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                all_results = data.get("results", [])

                # 过滤掉无效结果（没有内容或内容太短）
                valid_results = []
                for r in all_results[:15]:  # 检查前15个
                    content = r.get("content", "").strip()
                    # 跳过无效内容（放宽条件）
                    if content and len(content) > 10:  # 降低到10个字符
                        # 只过滤明显无用的内容
                        if ("doesn't work properly without JavaScript" in content or
                            "cannot provide a description" in content):
                            continue
                        valid_results.append(r)
                        if len(valid_results) >= 5:  # 增加到5个结果
                            break

                if valid_results:
                    summary = f"搜索'{query}'的结果：\n"
                    for i, r in enumerate(valid_results, 1):
                        title = r.get("title", "")
                        snippet = r.get("content", "")[:300]  # 增加到300字符
                        url = r.get("url", "")
                        summary += f"{i}. {title}\n   {snippet}\n"
                    logger.info(f"Web search '{query}' returned {len(valid_results)}/{len(all_results)} valid results")
                    return summary.strip()

            logger.warning(f"Web search '{query}' got no valid results (status={response.status_code})")
            return f"抱歉，搜索'{query}'没有找到有用的结果。建议换个关键词试试。"

        except Exception as e:
            logger.error(f"MCP web_search execution error: {e}")
            return f"抱歉，搜索'{query}'时出错了。"

    return None  # 未知的 MCP 工具


def execute_system_tool(name: str, arguments: dict) -> str:
    """执行系统工具并返回结果文本"""
    if name == "get_time" or name == "get_current_time":
        now = datetime.datetime.now()
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        year_cn = _year_to_chinese(now.year)
        return f"现在是 {year_cn}年{now.month}月{now.day}日 {weekday_cn} {now.strftime('%H:%M:%S')}"

    elif name == "get_date":
        now = datetime.datetime.now()
        year_cn = _year_to_chinese(now.year)
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        return f"今天是 {year_cn}年{now.month}月{now.day}日 {weekday_cn}"

    elif name == "exec_command":
        # 拦截命令执行请求，返回拒绝消息（避免传给 Codex sandbox 导致失败）
        return "抱歉，我无法执行系统命令。我只能提供时间日期等基本信息。"

    else:
        return None  # 未知工具，返回 None 表示不处理

def inject_system_tools(tools: list) -> list:
    """在现有工具列表中注入系统工具"""
    system_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "获取当前系统时间和日期。用户问几点了、现在几点、什么时候时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_date",
                "description": "获取今天的日期和星期。用户问今天几号、星期几时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]
    return system_tools + tools


def inject_mcp_tools(tools: list) -> list:
    """注入 MCP 工具定义（weather, web_search）"""
    mcp_tools = [
        {
            "type": "function",
            "function": {
                "name": "weather",
                "description": "查询指定地点的天气信息。用户问天气、会不会下雨时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称，如：北京、上海、深圳"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索网络信息。用于查询实时信息，包括：新闻、赛程、股价、汇率、产品价格、公司信息等。用户说'搜索'、'查询'、'找一下'时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词，例如：'AMD股价'、'NBA赛程'、'ChatGPT是什么'"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    return mcp_tools + tools

# ----------------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------------
@app.route("/v1/responses", methods=["POST"])
def responses():
    global _last_body
    try:
        body = request.get_json(force=True)
        _last_body = body  # 调试:保存最后一次请求
    except Exception as e:
        return Response(json.dumps({"error": {"message": f"bad json: {e}"}}),
                        status=400, content_type="application/json")

    model = MODEL_OVERRIDE or body.get("model", "")
    stream = bool(body.get("stream", False))
    max_out = body.get("max_output_tokens") or MAX_TOKENS
    max_out = max(max_out, MAX_TOKENS)
    temperature = body.get("temperature", TEMPERATURE)

    messages, tools = to_chat_messages(body)

    # DEBUG: 打印原始工具列表
    logger.info("DEBUG: Codex传来的原始工具数: %d", len(tools))
    if tools:
        tool_names = [t.get("function", {}).get("name") or t.get("name") for t in tools]
        logger.info("DEBUG: 工具名称列表: %s", tool_names)

    # 注入系统工具和 MCP 工具
    tools_with_system = inject_system_tools(tools)
    tools_all = inject_mcp_tools(tools_with_system)

    messages, last_user = apply_memory_and_cap(messages)

    # 添加系统提示强化工具使用（针对股价、汇率等查询）
    if last_user and any(keyword in last_user for keyword in ['股价', '汇率', '价格', 'stock', 'price']):
        # 在消息开头添加或增强系统消息
        has_system = any(m.get("role") == "system" for m in messages)
        tool_hint = "重要：当用户查询股价、汇率、价格等实时信息时，你必须使用web_search工具进行搜索，不要凭空回答。"

        if has_system:
            # 增强现有系统消息
            for m in messages:
                if m.get("role") == "system":
                    m["content"] = m["content"] + "\n" + tool_hint
                    break
        else:
            # 添加新的系统消息
            messages.insert(0, {"role": "system", "content": tool_hint})

    n_user = sum(1 for m in messages if m["role"] == "user")
    logger.info("responses: msgs=%d (user=%d) tools=%d stream=%s",
                len(messages), n_user, len(tools_all), stream)

    try:
        answer, tool_calls = call_vllm_chat(model, messages, tools_all, max_out, temperature)
    except Exception as e:
        logger.error("vLLM chat failed: %s", e)
        answer, tool_calls = "", None

    # 如果模型调了工具
    if tool_calls:
        # 尝试在代理侧执行系统工具
        system_tool_results = []
        other_tool_calls = []

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]

            # 优先尝试执行系统工具
            result = execute_system_tool(tool_name, tool_args)

            # 如果不是系统工具，尝试 MCP 工具
            if result is None:
                result = execute_mcp_tool(tool_name, tool_args)

            if result is not None:
                # 工具执行成功，记录结果
                system_tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })
                logger.info("Executed system tool: %s → %s", tool_name, result[:50])
            else:
                # 非系统工具，交给 Codex 处理
                other_tool_calls.append(tc)

        # 如果有系统工具被执行，用结果再次调用 LLM 获取最终回答
        if system_tool_results:
            messages_with_tool_results = messages + system_tool_results
            try:
                answer, _ = call_vllm_chat(model, messages_with_tool_results, [], max_out, temperature)
                logger.info("answer after system tool: %r", answer[:80])
            except Exception as e:
                logger.error("vLLM chat with tool results failed: %s", e)
                answer = system_tool_results[0]["content"]  # 直接返回工具结果

        # 如果还有其他工具调用，返回给 Codex 处理
        if other_tool_calls:
            logger.info("other_tool_calls: %s", json.dumps(other_tool_calls, ensure_ascii=False)[:200])
            # Codex Responses API 需要 function_call 类型 item
            fc_items = []
            for tc in other_tool_calls:
                fc_items.append({
                    "type": "function_call",
                    "id": tc["id"],
                    "call_id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                })
            rid = _rid()
            return Response(
                json.dumps(_base_response(rid, model, max_out, "completed", fc_items), ensure_ascii=False),
                content_type="application/json")

    # 否则返回文本回答
    if not answer:
        answer = "抱歉，我没有听清，可以再说一遍吗？"
    else:
        store_memory(last_user, answer)

    logger.info("answer: %r", answer[:80])

    if stream:
        return Response(synth_stream(answer, model, max_out),
                        content_type="text/event-stream")
    return Response(
        json.dumps(_base_response(_rid(), model, max_out, "completed",
                                  [_final_item(_mid(), answer)]), ensure_ascii=False),
        content_type="application/json")


@app.route("/v1/<path:subpath>", methods=["GET", "POST"])
def passthrough(subpath):
    url = f"{VLLM_BASE}/{subpath}"
    if request.method == "GET":
        r = _client.get(url, params=request.args)
    else:
        r = _client.post(url, content=request.get_data(),
                         headers={"Content-Type": request.content_type or "application/json"})
    return Response(r.content, status=r.status_code,
                    content_type=r.headers.get("content-type", "application/json"))


@app.route("/health", methods=["GET"])
def health():
    return Response('{"status":"ok"}', content_type="application/json")


def _warmup_memory():
    """后台预热嵌入模型,避免第一轮对话卡在模型加载(~17s)。"""
    try:
        _memory.warmup()
        logger.info("✓ memory model warmed up (%d items)", _memory.count())
    except Exception as e:
        logger.warning("memory warmup failed: %s", e)


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - codex_proxy - %(levelname)s - %(message)s")
    logger.info("Codex→vLLM proxy :%d → %s (memory=%s, max_turn_msgs=%d)",
                PORT, VLLM_BASE, MEMORY_ENABLED, MAX_TURN_MSGS)
    if _memory is not None:
        threading.Thread(target=_warmup_memory, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True)


if __name__ == "__main__":
    main()

# 临时调试端点:保存下一次 Codex 请求的完整 body
_last_body = None
@app.route("/debug/last_body", methods=["GET"])
def debug_last_body():
    global _last_body
    if _last_body:
        return Response(json.dumps(_last_body, indent=2, ensure_ascii=False), 
                       content_type="application/json")
    return Response('{"error":"no request yet"}', content_type="application/json")
