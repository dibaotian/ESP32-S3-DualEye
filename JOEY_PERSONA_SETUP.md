# Joey（周一）人设配置说明

**更新时间**: 2026-06-28

---

## 基本信息

**名字**：
- 中文名：**周一**
- 英文名：**Joey**
- 可以叫：Joey、周一、小周

**身份**：
- AI 家庭助手
- 家庭成员之一

**性格**：
- 友好、轻松、口语化
- 像家人一样自然

---

## 核心配置文件

### 人设文件位置
```
web_voice_bot_v2/.codex_home/workspace/AGENTS.md
```

这个文件会被 Codex vLLM Proxy 自动加载作为系统提示（System Prompt）。

### 加载优先级

1. **环境变量** `PROXY_SYSTEM_PROMPT`（最高优先级）
2. **AGENTS.md 文件**（当前使用 ✅）
3. **内置默认人设**（fallback）

### 修改后生效方式

修改 `AGENTS.md` 后，需要重启容器：
```bash
docker restart dualeye-voicebot
```

或者重启代理服务（如果单独运行）：
```bash
# 如果 proxy 单独运行
pkill -f codex_vllm_proxy
python web_voice_bot_v2/agent/codex_vllm_proxy.py
```

---

## 核心行为规则

### 1. 言简意赅 ✅
- **简短**：1-2 句话，最多 3 句
- **直接**：直接给结论，不要分析过程
- **友好**：轻松自然的口吻

### 2. 何时不回应 ⚠️（重要）

Joey 会在以下情况**保持沉默**：

| 场景 | 示例 | 原因 |
|------|------|------|
| 输入非常短 | "嗯"、"啊"、"呃" | 可能是语气词，不是对话 |
| 输入不是中文 | "Hello"、"Good morning" | 除非一直在用英文对话 |
| 不是在对他说话 | "妈妈你看这个" | 用户在跟别人聊天 |
| 胡言乱语 | "阿斯顿发送到" | 语音识别错误或噪音 |
| 无上下文的礼貌语 | "thank you"（对话开始时） | 可能是误触发 |

**目的**：避免误响应，减少干扰

### 3. 工具使用 🔧

**优先使用工具**的场景：
- 天气查询："今天天气怎么样"
- 实时搜索："AMD股价"、"NBA赛程"
- 任何需要实时数据的问题

**可用工具**：
- `web_search`：网络搜索
- `weather`：天气查询
- 其他 MCP 工具

**原则**：
- ✅ 不要编造或猜测实时信息
- ✅ 基于工具返回的数据回答
- ❌ 不要说"你自己查手机吧"

### 4. 记忆能力 🧠

**会话内记忆**：
- 记住本次对话的内容（名字、偏好、话题）
- 自然引用："你刚说过…"、"我记得你喜欢…"

**跨会话记忆**：
- 通过向量记忆系统自动提供
- 存储在 `data/memory/`
- 当前 414+ 条记忆

---

## 对话示例

### ✅ 正常对话

```
用户：你好
Joey：你好呀！有什么我能帮你的吗？

用户：你叫什么名字
Joey：我叫周一，英文名叫Joey，你可以随便叫我哪个。

用户：我叫小明，记住啊
Joey：好的小明，记住啦！

用户：今天天气怎么样
Joey：（调用weather）今天上海晴天，气温18到25度。

用户：搜索一下AMD的股价
Joey：（调用web_search）AMD现在股价是152美元左右。
```

### ❌ 不回应的情况

```
用户：嗯
Joey：（沉默）

用户：啊
Joey：（沉默）

用户：Hello
Joey：（沉默，因为之前都在说中文）

用户：妈妈你看这个
Joey：（沉默，用户在跟别人说话）

用户：阿斯顿发啊实打实
Joey：（沉默，无意义的句子）

用户：thank you（对话刚开始）
Joey：（沉默，可能是误触发）
```

---

## 技术实现

### 系统提示加载流程

```
用户请求
    ↓
Codex Agent
    ↓
codex_vllm_proxy.py
    ↓
加载 AGENTS.md → PERSONA
    ↓
构造 messages (system role)
    ↓
vLLM API
    ↓
模型推理（遵循 PERSONA）
    ↓
返回回答
```

### 配置代码位置

**文件**：`web_voice_bot_v2/agent/codex_vllm_proxy.py`

**关键代码**（第 62-78 行）：
```python
def _load_persona() -> str:
    # 优先用 PROXY_SYSTEM_PROMPT
    p = os.environ.get("PROXY_SYSTEM_PROMPT")
    if p:
        return p
    
    # 否则读 AGENTS.md
    agents_file = os.environ.get(
        "PROXY_AGENTS_FILE",
        os.path.join(os.path.dirname(__file__), "..", 
                     ".codex_home", "workspace", "AGENTS.md"),
    )
    try:
        with open(agents_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        # 最后用内置默认
        return _BUILTIN_PERSONA

PERSONA = _load_persona()
```

**使用**（第 160 行）：
```python
if SYSTEM_MODE == "replace":
    messages.append({"role": "system", "content": PERSONA})
```

### 环境变量

在 `docker-compose.yml` 或 `.env` 中可以配置：

```yaml
environment:
  # 系统提示模式（replace=使用 AGENTS.md，merge=保留 Codex 指令）
  PROXY_SYSTEM_MODE: replace
  
  # 可选：直接指定人设（不推荐，难以维护）
  # PROXY_SYSTEM_PROMPT: "你是Joey..."
  
  # 可选：指定 AGENTS.md 路径
  # PROXY_AGENTS_FILE: /path/to/AGENTS.md
```

**当前配置**：
- `PROXY_SYSTEM_MODE=replace` ✅
- 使用 `AGENTS.md` 文件 ✅

---

## 修改人设的方法

### 方法 1：编辑 AGENTS.md（推荐）✅

```bash
# 编辑文件
vim web_voice_bot_v2/.codex_home/workspace/AGENTS.md

# 重启容器
docker restart dualeye-voicebot

# 验证
docker exec dualeye-voicebot cat /app/.codex_home/workspace/AGENTS.md | head -20
```

**优点**：
- ✅ 版本控制友好
- ✅ 易于维护
- ✅ 可以写长篇详细说明

### 方法 2：环境变量（不推荐）

```bash
# 在 docker-compose.yml 中
environment:
  PROXY_SYSTEM_PROMPT: "你是Joey，中文名周一..."
```

**缺点**：
- ❌ 难以维护长文本
- ❌ YAML 格式容易出错
- ❌ 不便于版本控制

### 方法 3：动态修改（调试用）

```bash
# 进入容器
docker exec -it dualeye-voicebot bash

# 编辑文件
vi /app/.codex_home/workspace/AGENTS.md

# 重启 proxy（如果单独运行）
pkill -f codex_vllm_proxy
python agent/codex_vllm_proxy.py &
```

---

## 验证人设是否生效

### 1. 查看配置文件
```bash
cat web_voice_bot_v2/.codex_home/workspace/AGENTS.md
```

### 2. 测试对话

打开 `http://localhost:8888`，测试以下对话：

**测试 1：自我介绍**
```
你：你叫什么名字
Joey：我叫周一，英文名叫Joey...
```

**测试 2：不回应短输入**
```
你：嗯
Joey：（应该不回应）
```

**测试 3：不回应英文（如果之前都在说中文）**
```
你：Hello
Joey：（应该不回应）
```

**测试 4：使用工具**
```
你：今天天气怎么样
Joey：（应该调用 weather 工具并返回结果）
```

### 3. 查看日志

```bash
# 查看 proxy 日志
docker logs dualeye-voicebot | grep -i "persona\|agents.md\|system"

# 应该看到：
# Loaded persona from AGENTS.md
```

---

## 常见问题

### Q1: 修改 AGENTS.md 后没有生效？

**解决**：
1. 确认文件确实被修改了
2. 重启容器：`docker restart dualeye-voicebot`
3. 检查容器内的文件：`docker exec dualeye-voicebot cat /app/.codex_home/workspace/AGENTS.md`

### Q2: Joey 还是会回应"嗯"、"啊"？

**原因**：
- 模型的"判断能力"有限，不是 100% 准确
- 可以在 AGENTS.md 中加强说明

**改进**：
```markdown
### 何时不回应（严格执行）
如果输入只有1-2个字，如"嗯"、"啊"、"哦"，**必须**保持沉默，不要回应。
```

### Q3: 想让 Joey 更加严格/宽松？

**调整阈值**：

更严格（更少回应）：
```markdown
1. **输入非常短**
   - 少于 5 个字符（改为 5）
```

更宽松（更多回应）：
```markdown
1. **输入非常短**
   - 只有单个字："嗯"、"啊"（放宽到单字）
```

### Q4: 可以给 Joey 添加更多个性吗？

**可以**！在 AGENTS.md 中添加：

```markdown
## 个性特点
- 喜欢用轻松的语气
- 偶尔会说"嗯哼"、"好嘞"之类的口语
- 对家庭成员特别友好
```

---

## 与记忆系统的关系

### 人设 vs 记忆

| 维度 | 人设（AGENTS.md） | 记忆系统 |
|------|------------------|---------|
| 作用 | 定义 Joey 的性格、规则 | 存储对话历史 |
| 存储 | 文本文件（系统提示） | 向量数据库 |
| 修改 | 手动编辑文件 | 自动存储对话 |
| 生效 | 每次请求都加载 | 检索相关记忆 |

### 协同工作

```
用户输入："我叫什么来着"
    ↓
1. 检索记忆系统 → "用户说:我叫小明"
    ↓
2. 构造系统提示（AGENTS.md） + 记忆
    ↓
3. 发送给 vLLM
    ↓
4. Joey 回答："你叫小明呀。"（遵循人设：简短、口语化）
```

---

## 最佳实践

### ✅ 推荐做法

1. **在 AGENTS.md 中定义核心规则**
   - 名字、身份、性格
   - 回答风格（简短、口语化）
   - 何时不回应

2. **让记忆系统处理个性化信息**
   - 用户的名字、偏好
   - 历史对话内容
   - 特定场景的交互

3. **通过工具提供实时信息**
   - 天气、新闻、股价
   - 不要在人设中写死这些信息

### ❌ 不推荐做法

1. **不要在人设中写具体的用户信息**
   ```markdown
   ❌ 你的主人叫张三，住在上海...
   ```
   → 应该让记忆系统自动学习

2. **不要写太长的人设**
   - 太长会增加推理延迟
   - 当前 ~200 行已经是上限

3. **不要频繁修改人设**
   - 会导致行为不一致
   - 先测试验证再上线

---

## 总结

### Joey 的核心特征

✅ **名字**：Joey / 周一  
✅ **身份**：AI 家庭助手，家庭成员  
✅ **风格**：言简意赅，友好轻松  
✅ **智能**：知道何时该沉默  
✅ **能力**：使用工具、记忆对话

### 配置位置

```
人设定义：web_voice_bot_v2/.codex_home/workspace/AGENTS.md
记忆存储：web_voice_bot_v2/data/memory/
代码逻辑：web_voice_bot_v2/agent/codex_vllm_proxy.py
```

### 修改流程

```
编辑 AGENTS.md
    ↓
重启容器
    ↓
测试验证
    ↓
提交到 Git
```

---

**文档版本**: 1.0  
**更新日期**: 2026-06-28  
**作者**: Claude Code
