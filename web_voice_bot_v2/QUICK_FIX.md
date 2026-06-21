# 快速修复 - 麦克风和消息显示

## 🚀 立即尝试

### 步骤1: 检查浏览器控制台

1. 按 `F12` 打开开发者工具
2. 切换到 "Console" 标签
3. 点击"开始对话"
4. 说话
5. 查看是否有 `[Audio] Sending chunk` 日志

### 步骤2: 如果看不到音频日志

**刷新页面并检查**:
- 是否有红色错误
- AudioWorklet是否加载成功

### 步骤3: 查看后端日志

```bash
docker logs dualeye-voicebot -f
```

说话时应该看到:
```
Received audio chunk: ...
```

## 🐛 已知问题和解决方案

### 当前VAD问题

VAD模型在Docker中加载失败（GitHub rate limit）。

**临时解决方案**: 音频会累积但不会被VAD处理。

**永久修复**:
1. 修改代码跳过VAD
2. 或预先下载VAD模型

## 💬 确保消息显示

代码已更新，STT和LLM的输出会自动显示为：
- 蓝色气泡 = 你说的话（STT识别结果）
- 橙色气泡 = AI回复（LLM生成）

## 🔧 如果消息不显示

1. 打开浏览器控制台
2. 检查是否有 SocketIO 事件：
   ```
   [SocketIO] User message received: ...
   [SocketIO] LLM message received: ...
   ```
3. 如果有事件但不显示，刷新页面

## ⚡ 建议下一步

由于VAD在Docker中有问题，建议：

**方案A**: 修改代码移除VAD依赖
- 音频直接进入STT
- 需要重新构建镜像

**方案B**: 使用本地运行（非Docker）
- VAD可以正常工作
- 只能本机访问

**方案C**: 修复VAD Docker问题
- 预先下载模型到镜像

你想选择哪个方案？
