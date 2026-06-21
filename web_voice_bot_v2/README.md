# DualEye Voice Bot v2

超低延迟本地语音对话系统 - 基于 talk_with_llm_web_version 架构重构

## 架构设计

### Pipeline 流程
```
Browser (Mic) 
   ↓ WebSocket PCM 16kHz
Flask-SocketIO Server
   ↓ Queue
VAD (Silero)
   ↓ Queue
STT (ASR_Service - Qwen-ASR)
   ↓ Queue
LLM (vLLM Qwen3.5-35B-A3B-W4A16)
   ↓ Queue
TTS (MeloTTS)
   ↓ Queue
Audio Streamer
   ↓ WebSocket PCM 24kHz
Browser (Speaker)
```

### 技术栈

**后端**
- Flask + Flask-SocketIO: 实时双向通信
- Silero VAD: 语音活动检测
- ASR_Service (Qwen-ASR): 语音识别
- vLLM Qwen3.5-35B: 对话生成
- MeloTTS: 语音合成

**前端**
- WebAudio API + AudioWorklet: 低延迟音频处理
- SocketIO Client: 实时通信
- 现代响应式UI

## 快速开始

### 1. 安装依赖

```bash
cd web_voice_bot_v2
pip install -r requirements.txt
```

### 2. 启动后端服务

确保以下服务已运行：

**ASR Service (端口 8101)**
```bash
cd ../ASR_Service
# 按照 ASR_Service 的启动说明运行
```

**vLLM Service (端口 8102)**
```bash
cd ../vllm_Qwen3.5-35B-A3B-W4A16_Service
# 按照 vLLM Service 的启动说明运行
```

**Voice Bot Server (端口 8888)**
```bash
python app.py --host 0.0.0.0 --port 8888
```

### 3. 访问前端

HTTP访问:
```
http://localhost:8888
```

HTTPS访问 (推荐，WebAudio需要):
```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# 使用 SSL 启动
python app.py --ssl-cert cert.pem --ssl-key key.pem
```

访问: `https://localhost:8888`

## 配置参数

### VAD 参数
- `sample_rate`: 16000 (固定)
- `threshold`: 0.5 (语音检测阈值)
- `min_speech_duration_ms`: 250 (最短语音时长)
- `min_silence_duration_ms`: 500 (最短静音时长)

### STT 参数
- `api_url`: ASR Service API 地址
- `model`: Qwen/Qwen3-ASR-Flash
- `timeout`: 30秒

### LLM 参数
- `api_url`: vLLM API 地址
- `model`: cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit
- `temperature`: 0.7
- `max_tokens`: 512

### TTS 参数
- `language`: 'ZH' (中文)
- `speaker_id`: 0
- `speed`: 1.0
- `device`: 'auto' (自动选择 CUDA/CPU)

## 性能优化

### 延迟优化点

1. **VAD**: 实时流式检测，最小化语音端点检测延迟
2. **STT**: 使用轻量级 Qwen-ASR-Flash 模型
3. **LLM**: vLLM 高性能推理，支持 KV cache
4. **TTS**: MeloTTS 快速合成（约 0.2-0.5s RTF）
5. **传输**: WebSocket 二进制传输，分块流式播放

### 预期延迟

- VAD 检测: <100ms
- STT 识别: 200-500ms
- LLM 生成 (TTFT): 100-300ms
- TTS 合成: 200-500ms
- 网络传输: <50ms

**端到端延迟**: 通常 <1.5 秒

## 目录结构

```
web_voice_bot_v2/
├── app.py                      # 主服务器
├── base_handler.py             # Handler 基类
├── handlers/
│   ├── vad_handler.py          # VAD 处理器
│   ├── stt_handler.py          # STT 处理器
│   ├── llm_handler.py          # LLM 处理器
│   ├── tts_handler.py          # TTS 处理器
│   └── audio_streamer.py       # 音频流处理器
├── templates/
│   └── index.html              # 前端页面
├── static/
│   ├── css/
│   │   └── style.css           # 样式
│   └── js/
│       ├── app.js              # 主应用逻辑
│       └── audio-processor.js  # 音频处理 Worklet
├── requirements.txt            # Python 依赖
└── README.md                   # 本文档
```

## 故障排除

### 1. 麦克风无法访问
- 确保使用 HTTPS (或 localhost)
- 检查浏览器麦克风权限
- 尝试其他浏览器 (推荐 Chrome/Edge)

### 2. ASR/LLM 连接失败
- 检查对应服务是否运行
- 验证端口是否正确
- 查看服务日志

### 3. 音频播放问题
- 检查浏览器控制台错误
- 验证 SocketIO 连接状态
- 检查音频格式兼容性

## 日志

应用日志保存在 `voice_bot.log`

查看实时日志:
```bash
tail -f voice_bot.log
```

## 许可

MIT License

## 致谢

- 参考项目: [talk_with_llm_web_version](https://github.com/dibaotian/talk_with_llm_web_version)
- VAD: Silero VAD
- STT: Qwen-ASR
- LLM: Qwen3.5-35B
- TTS: MeloTTS
