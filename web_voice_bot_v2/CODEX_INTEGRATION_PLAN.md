# Codex 集成实施计划 (v1)

---
## ✅ 实施完成 (2026-06-22) —— 与原计划的一个重要差异

**原计划假设 Codex 能直连 vLLM,实测证明不行,必须加一个归一化代理。**

实测发现:
- Codex 0.135 删了 `wire_api="chat"`,只说 Responses API。
- 本地 vLLM(dev 版)的 `/v1/responses` 不认 `developer` 角色、要求 system 前置,
  且该 Qwen-W4A16 模型在此端点**无视 enable_thinking**,把 token 耗在思考上 →
  Codex 拿到空回复。
- 但同模型在 `/v1/chat/completions` + `enable_thinking=false` 上输出干净简短。

**解决方案:新增 `agent/codex_vllm_proxy.py`**(Responses ↔ ChatCompletions 适配):
Codex 用 Responses 收发,代理把请求转成 chat 打到 vLLM,再把干净回答合成回
Responses SSE 给 Codex。已实测跑通:多轮记忆 / resume / 服务器重启恢复 / reset。

**最终数据流**:
```
STT → CodexHandler → `codex exec` → 代理:8210 → vLLM:8102 /v1/chat/completions
                          ↑ thread 续接          (enable_thinking=false)
                     SessionManager(client_id→thread_id, 持久化)
```

**如何运行**(`python app.py` 会自动拉起代理):
- 默认 `AGENT_BACKEND=codex`;想回退旧直连用 `AGENT_BACKEND=vllm python app.py`。
- 依赖:vLLM 在 :8102、node/codex 在 PATH、Flask+httpx(venv 已有)。
- 验证过的能力:跨轮记忆、resume、重启恢复、reset 清忆、TTS 干净文本。

**已知 v1 局限**(后续阶段):每轮 `codex exec` 子进程开销;无 MCP 工具;
无向量长期记忆。详见文末。

---
## ⚡ 延迟实测与优化 (2026-06-22)

**第一次实测:每轮 ~5.3s。** 拆解后发现瓶颈不是进程启动(0.02s)也不是
vLLM 推理(0.25s),而是 **vLLM 每轮预填 Codex 注入的 26KB 编程 agent 系统
提示**(~7000 token → 4.4s)。

**关键优化:代理 `PROXY_SYSTEM_MODE=replace`(默认)** —— 丢弃 Codex 的
26KB 指令,换成我们 ~500 字的语音人设(来自 AGENTS.md)。纯对话场景不需要
Codex 的编程指令。效果:

| | merge (26KB) | replace (~500字) |
|---|---|---|
| 每轮 | ~5.3s | **~1.4s** |
| vLLM 上游 | 4.4s | 0.5–0.8s |

记忆 / resume / 重启恢复全部仍正常。**全链路预估 STT+Codex+TTS ≈ 2–2.4s/轮**,
满足语音对话。

**注:app-server 不能解决这个瓶颈**(26KB 是发给 vLLM 的,与 codex 是否常驻
无关)。replace 模式后,剩余 ~0.8s 才是 codex 自身机制,app-server 可再压一点,
但收益有限、复杂度高,暂不做。

---
## 🧠 向量长期记忆 + context 限长 (2026-06-22)

**问题**:Codex thread 随对话增长 → vLLM 预填变大 → 延迟回升 + 终将超窗口。

**方案**(全部在代理里,handler 不改):
1. **context 限长** `PROXY_MAX_TURN_MSGS`(默认 12 条)—— 只把最近 N 条对话发给
   vLLM → 延迟恒定,不随对话变长。
2. **向量长期记忆** `agent/memory_store.py`(numpy 实现,无 chromadb):
   - 每轮把 (用户问/答) 写入向量库;
   - 下轮按当前问题语义检索 top-k 旧记忆,注入 system 提示;
   - 嵌入模型 `BAAI/bge-small-zh-v1.5`(~95MB,CPU),启动时后台预热。

**实测**(窗口设 2 轮强制依赖记忆):
- T1 说"我对花生过敏" → 中间 3 轮无关闲聊(花生信息已出窗)→ T5 问"我能吃花生酱吗"
  → **"你刚说过你对花生过敏,所以不能吃花生酱哦"**(✓ 向量召回成功)
- 每轮延迟恒定 ~1.5s(窗口限长生效);首轮经预热也 ~1.4s。

**配置**(env):`PROXY_MEMORY=0` 关记忆;`PROXY_MAX_TURN_MSGS`、`MEMORY_TOPK`、
`MEMORY_EMBED_MODEL` 可调。记忆存在 `data/memory/`。

**v1 局限**:逐轮全量入库(含闲聊),靠相似度阈值过滤;后续可加 LLM 抽取"durable
事实"再入库,提升记忆质量。多用户需按 client_id 分库(已留 namespace 思路)。

---


**决策**: Codex 大脑 = 本地 vLLM (:8102) · 集成方式 = `codex exec` 子进程
**目标**: 用 Codex 替换 `LLMHandler`,获得持久化 thread(会话连贯 + 刷新安全 + 重启可恢复),
并预留多用户接口。单用户先跑通。

---

## v1 范围

✅ **本次做**:
- Codex 跑在本地 vLLM 上(隔离的 CODEX_HOME 配置,不污染你个人的 ~/.codex)
- 持久化 thread:同一对话连贯、页面刷新不丢、服务器重启可 resume
- 多用户接口预留(SessionManager 按 client_id 索引;单用户用 DEFAULT)
- 抽象 `AgentBackend`,以后能无痛切到 app-server 或加 Claude 后端

❌ **不在本次**(后续阶段):
- MCP 工具(天气/搜索)— Phase 2
- 向量长期记忆(Chroma)— Phase 3
- app-server 常驻进程低延迟优化 — Phase 4

---

## 关键技术事实(已实测验证)

| 项 | 结论 |
|----|------|
| Codex CLI | `@openai/codex@0.135.0` 已装,node v22 |
| 非交互模式 | `codex exec [PROMPT]`,`--json` 出 JSONL 事件,`-o <file>` 写最终回复 |
| thread_id 来源 | `--json` 流里的 `{"type":"thread.started","thread_id":"<uuid>"}` |
| 续接 thread | `codex exec resume <thread_id> "<prompt>"` |
| 失败检测 | `{"type":"turn.failed","error":{...}}` 事件 |
| session 落盘 | `~/.codex/sessions/YYYY/MM/DD/rollout-*-<uuid>.jsonl`(自动) |
| 当前认证 | AMD Gateway key 已失效(401)→ 改用本地 vLLM 绕开 |

---

## 文件改动

### 新增

```
web_voice_bot_v2/
├── .codex_home/
│   └── config.toml          # 隔离的 Codex 配置,指向本地 vLLM
├── AGENTS.md                # 语音助手人设 + 简洁/无 Markdown/工具策略
├── agent/
│   ├── __init__.py
│   ├── base.py              # AgentBackend 抽象基类
│   ├── codex_backend.py     # CodexBackend(用 codex exec / resume)
│   ├── session_manager.py   # client_id -> thread_id 映射(持久化)
│   └── text_utils.py        # strip_markdown(从 llm_handler 复用)
└── handlers/
    └── codex_handler.py     # 替换 LLMHandler,接 SessionManager + Backend
```

### 修改

- `app.py`:
  - `create_pipeline()` 里把 `LLMHandler` 换成 `CodexHandler`(同样的进出队列)
  - 新增 `@socketio.on('register')` 事件(存当前 client_id,单用户先用全局)
  - `reset` 事件同时重置该 client 的 codex session
  - 确保子进程 PATH 含 node/codex
- `.gitignore`:加 `.codex_home/`、`data/sessions.json`
- `requirements.txt`:v1 无新增 Python 依赖(纯 subprocess + stdlib)

---

## 核心组件设计

### 1. `.codex_home/config.toml`(Codex → 本地 vLLM)

```toml
model = "<vLLM 实际服务的模型名>"   # setup 时查 /v1/models 自动确定
model_provider = "local_vllm"
model_reasoning_effort = "minimal"  # 语音场景压低延迟

[model_providers.local_vllm]
name = "Local vLLM"
base_url = "http://localhost:8102/v1"
wire_api = "chat"                   # vLLM 走 OpenAI Chat Completions
```
> 用独立的 `CODEX_HOME=<project>/.codex_home` 跑子进程,**完全不动你个人的 ~/.codex**。

### 2. `agent/base.py` — 后端抽象

```python
class AgentResult(NamedTuple):
    answer: str
    thread_id: str

class AgentBackend(ABC):
    @abstractmethod
    def chat(self, thread_id: str | None, user_text: str) -> AgentResult:
        """thread_id=None → 新建会话;否则续接。返回回复 + (新)thread_id。"""
```

### 3. `agent/codex_backend.py` — Codex 子进程实现

- `chat(thread_id, text)`:
  - 新会话: `codex exec --json -s read-only --skip-git-repo-check -C <workdir> -o <tmp> "<text>"`
  - 续接: `codex exec resume <thread_id> --json ... -o <tmp> "<text>"`
  - 子进程 `env` 注入 `CODEX_HOME`、`PATH`(含 node)
  - 解析 `--json`:抓 `thread.started.thread_id`;遇 `turn.failed` 抛异常
  - 最终回复从 `-o` 文件读(最干净)
  - `timeout` 保护,异常向上抛

### 4. `agent/session_manager.py` — 多用户接口(核心)

```python
DEFAULT_CLIENT_ID = "default"

class SessionManager:
    def get(self, client_id) -> str | None      # 取 thread_id
    def set(self, client_id, thread_id) -> None  # 存映射 + 落盘
    def reset(self, client_id) -> None           # 清掉(下次新建会话)
    # 持久化到 data/sessions.json → 服务器重启后 resume 同一 thread
    # 线程安全(Lock)
```

### 5. `handlers/codex_handler.py` — 替换 LLMHandler

```python
def process(self, input_data):
    # 兼容: str(单用户) 或 {"client_id","text"}(未来多用户)
    client_id, text = self._parse(input_data)      # 现在恒为 DEFAULT
    thread_id = self.sessions.get(client_id)
    result = self.backend.chat(thread_id, text)    # 新建/续接
    self.sessions.set(client_id, result.thread_id)
    clean = strip_markdown(result.answer)          # TTS 友好
    if self.socketio: self.socketio.emit('llm_message', {'text': clean})
    return clean
    # 失败 → 返回中文兜底句
```

---

## 多用户演进路径(本次只留接口,不全接线)

现在管线是单一全局(全局 VAD、全局队列),所以单用户天然成立。
将来开多用户,只需 **3 处改动**:

1. `register` 事件按 `socket.id` 存 `sid -> client_id`(client_id 由前端 localStorage 固定 UUID 提供 → 刷新不丢)
2. STT 输出 payload 带上 client_id,贯穿队列到 CodexHandler
3. `audio_streamer` / `llm_message` 按 sid/room 定向下发

SessionManager 和 CodexHandler 的接口现在就按 client_id 设计,届时无需重构。

---

## 延迟与权衡(如实说明)

- `codex exec` 每轮起新 Node 进程 + 回放 session → **有进程启动开销(几百 ms~1s)**。
  v1 接受;v2 切 `app-server` 常驻进程消除。
- `model_reasoning_effort=minimal` + `-s read-only` 降低额外开销。
- 本地模型的 tool-calling 可靠性 < gpt-5.5,但 v1 不依赖工具,纯对话 + 会话记忆,够用。
- context 会随对话增长 → 后续用"向量库沉淀 + 裁剪 thread"解决(Phase 3)。

---

## 测试计划

1. **后端单测**:vLLM 在跑的前提下,`CodexBackend.chat(None, "我叫小明")` → 拿到 thread_id;
   `chat(thread_id, "我叫什么")` → 回 "小明"(验证 thread 续接)。
2. **端到端**:启动 vLLM + ASR + TTS,跑 `app.py`,说话验证多轮连贯。
3. **刷新安全**:对话中刷新页面,继续说,验证记忆不丢(thread 在服务端)。
4. **重启可恢复**:重启 app.py,验证 `sessions.json` 让同一 client resume 旧 thread。

---

## 已知风险 / setup 时确认

- vLLM 实际服务的**模型名**:setup 时查 `GET :8102/v1/models` 自动取,配置项兜底。
- vLLM 须正在运行;未运行时 CodexHandler 给出清晰报错(不静默失败)。
- 若 Codex 对本地模型的 `responses`/`chat` 兼容有问题,回退方案是 `wire_api` 调整或加
  `-c model_providers.local_vllm.*` 覆盖。
