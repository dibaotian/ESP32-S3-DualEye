# 快速开始指南

本指南将帮助你在5分钟内启动 DualEye Voice Bot v2。

## 前置要求

1. **已运行的服务**
   - ASR_Service (端口 8101)
   - vLLM Qwen3.5-35B Service (端口 8102)

2. **系统要求**
   - Python 3.10+
   - NVIDIA GPU (推荐，可选)
   - 4GB+ RAM

## 一键安装

```bash
cd web_voice_bot_v2
./install.sh
```

安装脚本将自动：
- 创建虚拟环境
- 安装 PyTorch (自动检测 CUDA)
- 安装所有依赖包
- 下载预训练模型

## 测试组件

安装完成后，运行测试脚本验证所有组件：

```bash
source venv/bin/activate
python test_components.py
```

你应该看到所有测试通过：
```
✓ PASS: PyTorch
✓ PASS: Flask-SocketIO
✓ PASS: Silero VAD
✓ PASS: MeloTTS
✓ PASS: ASR Service
✓ PASS: vLLM Service
```

## 启动服务器

### 方式1: 使用启动脚本 (推荐)

```bash
./start.sh
```

### 方式2: 手动启动

```bash
source venv/bin/activate
python app.py --host 0.0.0.0 --port 8888
```

### 方式3: HTTPS 模式 (推荐用于生产)

生成自签名证书:
```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

启动服务器:
```bash
python app.py --ssl-cert cert.pem --ssl-key key.pem
```

## 访问前端

浏览器打开:
- HTTP: `http://localhost:8888`
- HTTPS: `https://localhost:8888`

**注意**: WebAudio API 需要 HTTPS 或 localhost。如果通过局域网访问，请使用 HTTPS。

## 使用方法

1. 点击 **"开始对话"** 按钮
2. 允许浏览器访问麦克风
3. 开始说话
4. 系统会实时显示:
   - 你的语音识别结果 (蓝色气泡)
   - AI 的回复 (橙色气泡)
5. 同时播放 AI 的语音回复

## 性能调优

### GPU 内存不足

如果遇到 GPU OOM，可以调整以下参数:

**app.py**
```python
# 减少 TTS batch size 或使用 CPU
tts = TTSHandler(
    ...
    device='cpu',  # 改为 CPU
)
```

### 降低延迟

1. **VAD 灵敏度**: 减小 `threshold` 值 (默认 0.5)
2. **最短语音时长**: 减小 `min_speech_duration_ms` (默认 250ms)
3. **LLM tokens**: 减小 `max_tokens` (默认 512)

修改 `app.py` 中对应参数。

## 常见问题

### Q: 麦克风无法访问
A: 确保使用 HTTPS 或 localhost。检查浏览器权限设置。

### Q: ASR/LLM 连接失败
A: 
```bash
# 检查 ASR Service
curl http://localhost:8101/health

# 检查 vLLM Service
curl http://localhost:8102/health
```

### Q: 音频播放卡顿
A: 检查网络连接，增大前端音频缓冲区。

### Q: TTS 生成太慢
A: 
- 使用 GPU 加速
- 减小 LLM 生成的文本长度
- 考虑使用更快的 TTS 引擎 (如 Piper)

## 日志

查看实时日志:
```bash
tail -f voice_bot.log
```

## 下一步

- 调整系统提示词 (app.py 中的 `system_prompt`)
- 自定义前端样式 (static/css/style.css)
- 添加对话历史保存功能
- 集成更多 TTS 语音选项

## 获取帮助

遇到问题？
1. 查看日志文件 `voice_bot.log`
2. 运行测试脚本 `python test_components.py`
3. 检查依赖服务状态

祝你使用愉快！🎉
