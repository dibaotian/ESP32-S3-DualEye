# 记忆系统使用指南

## 系统架构

### 当前实现：向量长期记忆

Web Voice Bot V2 使用**向量语义检索**的长期记忆系统，可以跨对话记住重要信息。

```
用户输入
    ↓
1. 向量检索 (recall) - 查找相关历史记忆
    ↓
2. 注入系统提示 - 把相关记忆告诉模型
    ↓
3. 模型回答
    ↓
4. 存储记忆 (add) - 保存这轮对话
```

## 核心组件

### 1. VectorMemory 类
**文件**: `web_voice_bot_v2/agent/memory_store.py`

**功能**:
- **嵌入模型**: BAAI/bge-small-zh-v1.5 (中文优化，95MB)
- **存储格式**: 
  - `embeddings.npy` - 向量矩阵 (float32)
  - `docs.json` - 文本内容 + 元数据
- **检索方法**: 余弦相似度 Top-K

**API**:
```python
from memory_store import VectorMemory

# 初始化
memory = VectorMemory("/path/to/memory/dir")

# 添加记忆
memory.add("用户说:你叫什么名字 | 助手答:我叫小林", meta={"time": "2026-06-28"})

# 检索记忆
results = memory.recall("小林是谁", k=3, min_score=0.35)
# 返回: ['用户说:你叫什么名字 | 助手答:我叫小林', ...]

# 统计
count = memory.count()  # 407 条
```

### 2. Proxy 集成
**文件**: `web_voice_bot_v2/agent/codex_vllm_proxy.py`

**流程**:

#### 检索记忆 (第 328-353 行)
```python
def apply_memory_and_cap(messages):
    """限制最近对话条数 + 注入相关长期记忆"""
    # 1. 提取最后一条用户消息
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"]
            break
    
    # 2. 检索相关记忆
    if _memory is not None and last_user:
        mems = _memory.recall(last_user, k=MEMORY_TOPK)  # k=3
        if mems:
            # 3. 注入到 system 消息
            sys_text += "\n\n[你记得的相关信息]\n" + "\n".join(f"- {m}" for m in mems)
    
    return [{"role": "system", "content": sys_text}] + capped, last_user
```

#### 存储记忆 (第 356-362 行)
```python
def store_memory(last_user: str, answer: str):
    """每轮对话后保存"""
    if _memory is None or not last_user:
        return
    _memory.add(f"用户说:{last_user} | 助手答:{answer}")
```

## 配置参数

### 环境变量

**文件**: `.env` 或 Docker 环境变量

```bash
# 启用/禁用记忆 (默认启用)
PROXY_MEMORY=1

# 记忆存储目录 (默认: data/memory/)
MEMORY_DIR=/app/data/memory

# 检索 Top-K 数量 (默认: 3)
MEMORY_TOPK=3

# 嵌入模型 (默认: BAAI/bge-small-zh-v1.5)
MEMORY_EMBED_MODEL=BAAI/bge-small-zh-v1.5

# 最大对话轮数 (默认: 12, 限制短期对话长度)
PROXY_MAX_TURN_MSGS=12
```

### 当前配置

```bash
docker exec dualeye-voicebot env | grep -E "PROXY_MEMORY|MEMORY"
```

当前值:
- PROXY_MEMORY=1 ✅ 已启用
- MEMORY_TOPK=3 (每次检索 3 条相关记忆)
- MAX_TURN_MSGS=12 (保留最近 12 轮对话)

## 记忆存储位置

### 容器内
```
/app/data/memory/
├── embeddings.npy    # 815KB - 向量矩阵
└── docs.json         # 76KB - 文本内容
```

### 宿主机
```
/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/
```

### 当前状态
- **记忆总数**: 407 条
- **最后更新**: 2026-06-28 21:32

## 如何增加记忆

### 方法 1: 自动记忆（已启用）✅

**默认行为**: 每轮对话自动保存

```
用户: "我的名字叫张三"
助手: "好的，张三！"
    ↓
自动保存: "用户说:我的名字叫张三 | 助手答:好的，张三！"
```

**下次查询**:
```
用户: "我叫什么名字"
    ↓
检索记忆: ["用户说:我的名字叫张三 | 助手答:好的，张三！"]
    ↓
助手: "你叫张三。"
```

**注意**: 这种记忆是**语义检索**的，不是关键词匹配！

### 方法 2: 手动添加记忆

#### 2.1 通过 Python 脚本

创建 `add_memory.py`:
```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2')

from agent.memory_store import VectorMemory

# 初始化记忆库
memory = VectorMemory("/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory")

# 添加记忆
memories = [
    "用户说:我的生日是3月15日 | 助手答:记住了，你的生日是3月15日",
    "用户说:我最喜欢的颜色是蓝色 | 助手答:好的，蓝色是你的最爱",
    "用户说:我住在上海浦东 | 助手答:知道了，你住在上海浦东",
]

for mem in memories:
    memory.add(mem)
    print(f"✅ 已添加: {mem[:50]}...")

print(f"\n总记忆数: {memory.count()}")
```

运行:
```bash
python3 add_memory.py
```

#### 2.2 通过容器内执行

```bash
docker exec dualeye-voicebot python3 << 'EOF'
import sys
sys.path.insert(0, '/app')
from agent.memory_store import VectorMemory

memory = VectorMemory("/app/data/memory")
memory.add("用户说:我的车牌号是沪A12345 | 助手答:记住了，沪A12345")
print(f"✅ 添加成功，总数: {memory.count()}")
EOF
```

#### 2.3 批量导入 JSON

创建 `memories.json`:
```json
[
  {
    "user": "我的工作是软件工程师",
    "assistant": "明白了，你是做软件开发的"
  },
  {
    "user": "我有一只叫小白的猫",
    "assistant": "好可爱，你的猫叫小白"
  },
  {
    "user": "我每天早上7点起床",
    "assistant": "知道了，你的作息时间很规律"
  }
]
```

导入脚本 `import_memories.py`:
```python
#!/usr/bin/env python3
import json
import sys
sys.path.insert(0, '/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2')

from agent.memory_store import VectorMemory

memory = VectorMemory("/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory")

with open('memories.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    text = f"用户说:{item['user']} | 助手答:{item['assistant']}"
    memory.add(text)
    print(f"✅ {text[:60]}...")

print(f"\n总记忆数: {memory.count()}")
```

### 方法 3: 结构化记忆（推荐）

为了更好的检索效果，使用结构化格式：

```python
from agent.memory_store import VectorMemory
import datetime

memory = VectorMemory("/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory")

# 个人信息
memory.add(
    "用户说:我的全名是张三，手机号13912345678 | 助手答:记住了，张三 139-1234-5678",
    meta={"category": "personal_info", "time": datetime.datetime.now().isoformat()}
)

# 偏好设置
memory.add(
    "用户说:我不喜欢吃香菜 | 助手答:好的，点菜时会注意避开香菜",
    meta={"category": "preferences"}
)

# 日程安排
memory.add(
    "用户说:明天下午3点有个会议 | 助手答:好的，已记下明天15:00的会议",
    meta={"category": "schedule", "date": "2026-06-29"}
)

# 设备控制偏好
memory.add(
    "用户说:卧室灯默认亮度设为50% | 助手答:记住了，卧室灯默认50%亮度",
    meta={"category": "device_preference", "device": "bedroom_light"}
)
```

## 查看记忆

### 查看所有记忆

```python
#!/usr/bin/env python3
import json

with open('/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/docs.json', 'r', encoding='utf-8') as f:
    docs = json.load(f)

print(f"总记忆数: {len(docs)}\n")

# 查看最近 10 条
for i, doc in enumerate(docs[-10:], 1):
    print(f"{len(docs)-10+i}. {doc['text']}")
    if doc.get('meta'):
        print(f"   元数据: {doc['meta']}")
    print()
```

### 搜索记忆

```python
from agent.memory_store import VectorMemory

memory = VectorMemory("/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory")

# 语义搜索
results = memory.recall("我的名字", k=5)
for i, r in enumerate(results, 1):
    print(f"{i}. {r}")
```

### 导出记忆

```bash
# 复制记忆文件到本地
docker cp dualeye-voicebot:/app/data/memory/docs.json ./memory_backup.json

# 查看
cat memory_backup.json | python3 -m json.tool | less
```

## 清除记忆

### 清除所有记忆

```bash
# 停止容器
docker stop dualeye-voicebot

# 删除记忆文件
rm /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/*.npy
rm /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/*.json

# 重启容器
docker start dualeye-voicebot
```

### 删除特定记忆

```python
import json

# 读取
with open('/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/docs.json', 'r', encoding='utf-8') as f:
    docs = json.load(f)

# 过滤（删除包含"股价"的记忆）
filtered = [doc for doc in docs if '股价' not in doc['text']]

print(f"删除了 {len(docs) - len(filtered)} 条记忆")

# 保存
with open('/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/docs.json', 'w', encoding='utf-8') as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

# 需要重新生成 embeddings.npy
# 最简单的方法：删除 embeddings.npy，重启容器让系统重建
```

## 高级配置

### 调整检索数量

更多上下文 vs 更快响应：

```bash
# 在 docker-compose.yml 中设置
environment:
  - MEMORY_TOPK=5  # 增加到 5 条（更多上下文）
```

重启容器生效。

### 调整相似度阈值

**文件**: `agent/memory_store.py` 第 97 行

```python
def recall(self, query: str, k: int = 3, min_score: float = 0.35) -> List[str]:
    # min_score: 最低相似度
    # 0.35 = 较宽松（可能检索到不太相关的）
    # 0.50 = 中等
    # 0.70 = 严格（只返回高度相关的）
```

修改后需要重启容器。

### 更换嵌入模型

```bash
# 使用更大的模型（更好但更慢）
MEMORY_EMBED_MODEL=BAAI/bge-large-zh-v1.5

# 使用多语言模型
MEMORY_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**注意**: 更换模型后需要**重新生成所有 embeddings**！

## 记忆的工作原理

### 存储格式

每条记忆存储为：
```
"用户说:<用户输入> | 助手答:<助手回答>"
```

例如：
```
"用户说:我的名字叫张三 | 助手答:好的，张三！"
```

### 检索过程

1. **用户输入**: "我叫什么名字"
2. **向量化**: 转换为 384 维向量 (bge-small-zh)
3. **余弦相似度**: 与所有记忆计算相似度
4. **Top-K**: 选出最相似的 3 条
5. **阈值过滤**: 只保留相似度 ≥ 0.35 的
6. **注入提示**: 添加到 system 消息

### 示例

```
用户: "我最喜欢什么颜色"

检索到的记忆:
1. 用户说:我最喜欢的颜色是蓝色 | 助手答:好的，蓝色是你的最爱 (相似度: 0.89)
2. 用户说:我不喜欢红色 | 助手答:知道了，你不喜欢红色 (相似度: 0.52)
3. 用户说:我的房间墙是蓝色的 | 助手答:蓝色的墙很舒适 (相似度: 0.41)

System 提示:
  你是一个语音助手...
  
  [你记得的相关信息]
  - 用户说:我最喜欢的颜色是蓝色 | 助手答:好的，蓝色是你的最爱
  - 用户说:我不喜欢红色 | 助手答:知道了，你不喜欢红色
  - 用户说:我的房间墙是蓝色的 | 助手答:蓝色的墙很舒适

助手回答: "你最喜欢蓝色。"
```

## 最佳实践

### 1. 记忆什么

✅ **应该记住的**:
- 个人信息（姓名、生日、联系方式）
- 偏好设置（喜好、习惯）
- 重要事实（家庭成员、宠物、工作）
- 设备控制偏好
- 常用指令

❌ **不应该记住的**:
- 敏感信息（密码、银行账号）
- 临时查询（"今天天气"）
- 工具调用结果（搜索结果）
- 系统错误信息

### 2. 记忆格式

**推荐格式**:
```
用户说:<简洁的事实陈述> | 助手答:<确认或补充>
```

**示例**:
```
✅ 用户说:我的生日是3月15日 | 助手答:记住了，3月15日
❌ 用户说:嗯嗯啊啊那个我的生日好像是...3月15日吧 | 助手答:好的好的我知道了
```

### 3. 定期维护

```bash
# 查看记忆数量
docker exec dualeye-voicebot python3 -c "
from agent.memory_store import VectorMemory
m = VectorMemory('/app/data/memory')
print(f'记忆数: {m.count()}')
"

# 当记忆数超过 1000 条时，考虑清理不重要的
# 建议每月备份一次
```

## 故障排除

### 问题 1: 记忆没有被检索

**检查**:
```bash
docker logs dualeye-voicebot | grep "recalled"
```

应该看到：
```
recalled 3 memory item(s)
```

如果看到 `recalled 0`，可能是：
- 相似度太低（没有相关记忆）
- 阈值太高（min_score=0.35）

### 问题 2: 记忆没有被保存

**检查**:
```bash
# 查看最后修改时间
ls -lh /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/

# 应该看到最近的时间戳
```

如果文件没有更新：
- 检查权限：`sudo chown -R xilinx:xilinx data/memory/`
- 检查日志：`docker logs dualeye-voicebot | grep "memory store failed"`

### 问题 3: 记忆加载失败

**日志**:
```
Failed to load memory: ...
```

**解决**:
```bash
# 删除损坏的文件
rm /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/*.npy

# 重启容器重建
docker restart dualeye-voicebot
```

## 与 Codex Memory 的区别

### Codex 的内置记忆

Codex CLI 也有记忆系统（`.codex_home/memory/`），但：
- 用于**代码编程场景**（文件路径、函数名、调试历史）
- 存储格式不同

### Web Voice Bot 的记忆

- 用于**语音对话场景**（个人信息、偏好、事实）
- 针对中文优化
- 轻量快速

**两者独立**，不冲突。

## 进阶：自定义记忆策略

### 分类存储

```python
class CategorizedMemory:
    def __init__(self, base_dir):
        self.personal = VectorMemory(f"{base_dir}/personal")
        self.preferences = VectorMemory(f"{base_dir}/preferences")
        self.schedule = VectorMemory(f"{base_dir}/schedule")
    
    def add_personal(self, text):
        self.personal.add(text, meta={"category": "personal"})
    
    def recall_all(self, query, k=3):
        # 从所有类别检索
        results = []
        results.extend(self.personal.recall(query, k=k))
        results.extend(self.preferences.recall(query, k=k))
        results.extend(self.schedule.recall(query, k=k))
        return results[:k]
```

### 时间衰减

```python
import time

def add_with_timestamp(memory, text):
    memory.add(text, meta={"timestamp": time.time()})

def recall_with_decay(memory, query, k=3, decay_days=30):
    # 检索时考虑时间衰减
    # 30天前的记忆权重降低
    pass  # 需要自定义实现
```

## 总结

### 快速开始

1. **查看当前记忆**:
   ```bash
   python3 -c "
   import json
   docs = json.load(open('/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory/docs.json'))
   print(f'记忆数: {len(docs)}')
   "
   ```

2. **添加新记忆**:
   ```bash
   docker exec dualeye-voicebot python3 -c "
   import sys; sys.path.insert(0, '/app')
   from agent.memory_store import VectorMemory
   m = VectorMemory('/app/data/memory')
   m.add('用户说:我的名字叫XXX | 助手答:记住了')
   print('✅ 添加成功')
   "
   ```

3. **测试检索**:
   ```bash
   docker exec dualeye-voicebot python3 -c "
   import sys; sys.path.insert(0, '/app')
   from agent.memory_store import VectorMemory
   m = VectorMemory('/app/data/memory')
   results = m.recall('我叫什么', k=3)
   for r in results: print(r)
   "
   ```

### 关键文件

- **记忆实现**: `agent/memory_store.py`
- **集成逻辑**: `agent/codex_vllm_proxy.py` (第 328-362 行)
- **存储位置**: `data/memory/docs.json` + `embeddings.npy`
- **配置**: 环境变量 `MEMORY_TOPK`, `PROXY_MEMORY`

---

**文档版本**: 2026-06-28  
**记忆系统版本**: v1.0 (向量检索)  
**当前记忆数**: 407 条
