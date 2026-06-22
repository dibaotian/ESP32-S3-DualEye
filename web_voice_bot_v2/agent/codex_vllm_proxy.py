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
    system_texts = []
    if SYSTEM_MODE == "merge" and body.get("instructions"):
        system_texts.append(str(body["instructions"]))

    convo = []
    for it in body.get("input", []) or []:
        if not isinstance(it, dict):
            continue
        if it.get("type", "message") != "message":
            continue  # 丢 reasoning / function_call / ...
        role = it.get("role")
        text = _item_text(it)
        if role in ("system", "developer"):
            if SYSTEM_MODE == "merge":
                system_texts.append(text)
            # replace 模式:丢弃 Codex 注入的所有 system/developer 内容(含 26KB 指令)
        elif role in ("user", "assistant"):
            convo.append({"role": role, "content": text})

    messages = []
    if SYSTEM_MODE == "replace":
        messages.append({"role": "system", "content": PERSONA})
    else:
        merged = "\n\n".join(t for t in system_texts if t and t.strip())
        if merged:
            messages.append({"role": "system", "content": merged})
    messages.extend(convo)
    return messages


# ----------------------------------------------------------------------------
# 调 vLLM chat/completions 拿干净回答
# ----------------------------------------------------------------------------
def call_vllm_chat(model: str, messages, max_tokens: int, temperature: float) -> str:
    req = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    sys_chars = sum(len(m.get("content", "")) for m in messages if m.get("role") == "system")
    _t = time.time()
    r = _client.post(f"{VLLM_BASE}/chat/completions", json=req)
    r.raise_for_status()
    logger.info("upstream vLLM call: %.2fs (system_chars=%d)", time.time() - _t, sys_chars)
    content = r.json()["choices"][0]["message"]["content"]
    return strip_thinking(content)


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
# 路由
# ----------------------------------------------------------------------------
@app.route("/v1/responses", methods=["POST"])
def responses():
    try:
        body = request.get_json(force=True)
    except Exception as e:
        return Response(json.dumps({"error": {"message": f"bad json: {e}"}}),
                        status=400, content_type="application/json")

    model = MODEL_OVERRIDE or body.get("model", "")
    stream = bool(body.get("stream", False))
    max_out = body.get("max_output_tokens") or MAX_TOKENS
    max_out = max(max_out, MAX_TOKENS)
    temperature = body.get("temperature", TEMPERATURE)

    messages = to_chat_messages(body)
    messages, last_user = apply_memory_and_cap(messages)
    n_user = sum(1 for m in messages if m["role"] == "user")
    logger.info("responses: msgs=%d (user=%d) stream=%s max_out=%d",
                len(messages), n_user, stream, max_out)

    try:
        answer = call_vllm_chat(model, messages, max_out, temperature)
    except Exception as e:
        logger.error("vLLM chat failed: %s", e)
        answer = ""
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
