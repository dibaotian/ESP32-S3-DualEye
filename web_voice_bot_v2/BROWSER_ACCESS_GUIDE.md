# 浏览器访问指南

## 🎯 当前服务器状态

✅ **服务器正在运行！**

- **主机**: 0.0.0.0 (所有网络接口)
- **端口**: 8888
- **模式**: 文本模式 (TTS暂未启用)
- **进程状态**: 后台运行中

## 🌐 访问地址

### 本地访问 (推荐用于开发)

```
http://localhost:8888
http://127.0.0.1:8888
```

### 局域网访问

从同一局域网的其他设备访问：

```
http://10.161.176.132:8888
```

**注意**: 
- WebAudio API 需要 HTTPS 或 localhost
- 如果从其他设备访问，麦克风可能无法使用
- 建议使用 localhost 或配置 HTTPS

## 🔧 如果无法访问

### 1. 检查服务器状态

```bash
# 检查进程
ps aux | grep "python.*app.py"

# 检查端口
netstat -tuln | grep 8888

# 查看日志
tail -f voice_bot.log
```

### 2. 重启服务器

```bash
# 停止服务器
pkill -f "python.*app.py"

# 重新启动
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
nohup venv/bin/python app.py --port 8888 > voice_bot_server.log 2>&1 &

# 验证启动
sleep 3
curl http://localhost:8888
```

### 3. 检查防火墙

```bash
# 检查防火墙规则 (如果启用)
sudo ufw status

# 如需开放端口
sudo ufw allow 8888/tcp
```

## 📱 使用方式

### 当前功能 (无TTS模式)

1. ✅ 打开浏览器访问上述地址
2. ✅ 点击 "开始对话" 按钮
3. ✅ 允许麦克风权限
4. ✅ 开始说话
5. ✅ 查看识别结果 (蓝色气泡)
6. ✅ 查看AI回复 (橙色气泡)
7. ❌ 暂无语音播放 (需要安装TTS)

### 完整功能 (需要启用TTS)

安装TTS后，将额外支持：
8. ✅ 播放AI语音回复

## 🔐 HTTPS 配置 (可选)

如果需要从局域网其他设备使用麦克风：

```bash
# 1. 生成自签名证书
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365 \
  -subj "/CN=10.161.176.132"

# 2. 停止当前服务器
pkill -f "python.*app.py"

# 3. 使用SSL启动
venv/bin/python app.py --port 8888 \
  --ssl-cert cert.pem --ssl-key key.pem &

# 4. 访问 (注意是 https)
# https://10.161.176.132:8888
```

**注意**: 浏览器会警告证书不受信任，点击"继续访问"即可。

## 🎨 界面预览

打开后您将看到：

```
┌─────────────────────────────────────────┐
│  🎙️ DualEye Voice Bot                  │
│  超低延迟本地语音对话系统                │
├─────────────────────────────────────────┤
│                                         │
│  [聊天消息区域]                          │
│                                         │
│  👤 用户: 你好                          │
│  🤖 AI: 你好！有什么可以帮助你的吗？    │
│                                         │
├─────────────────────────────────────────┤
│  [🎤 开始对话]  [🔄 重置]               │
├─────────────────────────────────────────┤
│  ● 已连接                               │
└─────────────────────────────────────────┘
```

## 📊 性能监控

### 实时查看日志

```bash
# 应用日志
tail -f voice_bot.log

# 服务器日志
tail -f voice_bot_server.log
```

### 浏览器开发者工具

按 `F12` 打开开发者工具查看：
- Network: WebSocket连接状态
- Console: 前端日志和错误
- Performance: 音频处理性能

## ⚡ 性能指标

当前系统性能：

| 指标 | 数值 | 说明 |
|------|------|------|
| ASR延迟 | ~67ms | 语音识别 |
| LLM TTFT | ~150ms | 首个响应token |
| 端到端 | ~370ms | 无TTS模式 |
| 目标延迟 | <1秒 | 含TTS |

## 🐛 常见问题

### Q: 麦克风无法访问
**A**: 
- 确保使用 `localhost` 或 HTTPS
- 检查浏览器权限设置
- 尝试 Chrome/Edge (推荐)

### Q: 页面加载但无响应
**A**:
- 检查 ASR/vLLM 服务是否运行
- 查看浏览器控制台错误
- 检查服务器日志

### Q: WebSocket连接失败
**A**:
- 确认服务器正在运行
- 检查防火墙设置
- 验证端口8888未被占用

### Q: 识别不准确
**A**:
- 检查麦克风质量
- 在安静环境测试
- 调整VAD参数 (app.py)

## 📝 日志级别

修改 `app.py` 中的日志级别：

```python
logging.basicConfig(
    level=logging.INFO,  # 改为 DEBUG 查看详细日志
    ...
)
```

## 🔄 服务器管理

### 查看服务器信息

```bash
# PID
pgrep -f "python.*app.py"

# 资源占用
top -p $(pgrep -f "python.*app.py")
```

### 优雅停止

```bash
# 发送SIGTERM
pkill -TERM -f "python.*app.py"

# 等待几秒
sleep 3

# 强制停止 (如果需要)
pkill -9 -f "python.*app.py"
```

---

**当前状态**: ✅ 服务器运行中，可以访问 http://localhost:8888

**下一步**: 打开浏览器，开始测试语音对话功能！
