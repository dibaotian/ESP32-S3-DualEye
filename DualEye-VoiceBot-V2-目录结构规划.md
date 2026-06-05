# DualEye VoiceBot V2 — 目录结构规划

> **日期**: 2026-04-07  
> **基于**: V1 规划 + 实际开发演化  
> **状态**: V1 → V2 架构差异总结 + V2 目标结构

---

## 1. V1 → V2 架构演化总结

### 1.1 通信架构变更

| 维度 | V1 规划 | V2 实际 |
|------|---------|---------|
| ESP32 ↔ 主机 | micro-ROS (DDS over UDP) | **直连 TCP+UDP Socket** |
| 控制通道 | ROS 2 Topics (String) | **TCP:3000 JSON** |
| 音频通道 | ROS Topic (Base64 编码) | **UDP:3001 裸 PCM** |
| 主机内部 | ROS 2 DDS 节点通信 | **单进程 asyncio 管线** |
| 音频编码 | Base64 (33% 开销) | **原始 PCM (零开销)** |

### 1.2 主机架构变更

| 维度 | V1 规划 | V2 实际 |
|------|---------|---------|
| 架构 | 多 ROS 2 节点 (Orchestrator/STT/LLM/TTS) | **单文件 voicebot_server.py (~5300行)** |
| STT | faster-whisper (Python) | **whisper.cpp server (Vulkan GPU, HTTP)** |
| LLM | Ollama / OpenAI API | **vLLM + Qwen3.5-35B-A3B-AWQ (ROCm)** |
| TTS | edge-tts (在线) | **Piper HTTP 本地 / CosyVoice2 备选** |
| 唤醒 | ESP32 本地 ESP-AFE | 同 (ESP-AFE "Hi ESP") |
| 新功能 | — | **Tool-call、对话记忆、天气查询、streaming STT、LLM prefetch、endpoint detection** |

### 1.3 固件架构变更

| 维度 | V1 规划 | V2 实际 |
|------|---------|---------|
| 通信 | micro-ROS 节点 | **TCP/UDP Socket (comm_protocol.c)** |
| 音频 | AFE + ROS Topic 分块 | **AFE + speech gate → UDP 流式** |
| 状态机 | 简单 FSM (事件队列) | **state_machine.c + follow-up listen** |
| 眼睛 | LVGL Canvas 自绘 | **LVGL 动画 (eye_animation.c)** |
| 组件化 | components/ 分离 | **main/ 平铺 + drivers/ 子目录** |

---

## 2. V2 目录结构（目标）

```
ESP32-S3-DualEye/                              # 项目根目录
│
├── DualEye-VoiceBot-项目规划.md                 # V1 原始规划文档
├── DualEye-VoiceBot-V2-目录结构规划.md          # 本文档
├── env_setup_manual.md                         # 环境搭建手册
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │                      ESP32 固件                              │
│  └─────────────────────────────────────────────────────────────┘
│
├── DualEye-ESP32S3-Firmware-Pack/              # ESP32-S3 固件工程
│   ├── README.md                               # 固件说明、烧录步骤
│   ├── env_setup_manual.md                     # ESP-IDF 环境搭建
│   ├── firmware/                               # ESP-IDF 工程根
│   │   ├── CMakeLists.txt                      # 顶层构建
│   │   ├── sdkconfig                           # 当前配置
│   │   ├── sdkconfig.defaults                  # 默认配置
│   │   ├── partitions.csv                      # Flash 分区表
│   │   ├── main/
│   │   │   ├── CMakeLists.txt
│   │   │   ├── Kconfig.projbuild              # WiFi SSID/密码等可配置项
│   │   │   ├── board_config.h                 # GPIO / 硬件引脚定义
│   │   │   │
│   │   │   ├── main.c                         # app_main() 入口、任务创建
│   │   │   ├── state_machine.c/.h             # 核心 FSM (IDLE→WAKEUP→LISTENING→THINKING→SPEAKING)
│   │   │   ├── audio_pipeline.c/.h            # 录音管线: ESP-AFE → speech gate → UDP 发送
│   │   │   ├── comm_protocol.c/.h             # TCP JSON 控制 + UDP PCM 音频收发
│   │   │   ├── eye_animation.c/.h             # LVGL 双屏眼睛动画 (表情状态)
│   │   │   ├── wifi_manager.c/.h              # WiFi STA 连接管理
│   │   │   │
│   │   │   ├── drivers/                       # 底层硬件驱动
│   │   │   │   ├── i2c_driver.c/.h            # I2C 总线 (ES8311/ES7210/CST816)
│   │   │   │   ├── i2s_audio.c/.h             # I2S TX(播放)/RX(录音) + DMA
│   │   │   │   ├── lcd_driver.c/.h            # GC9A01A 双屏 SPI 驱动
│   │   │   │   └── lvgl_port.c/.h             # LVGL 初始化 + 双屏 flush 回调
│   │   │   │
│   │   │   └── test_*.c                       # 硬件调试用例 (PA/codec/speaker)
│   │   │
│   │   ├── build/                             # 构建输出 (gitignore)
│   │   └── managed_components/                # ESP-IDF 组件管理器依赖
│   │
│   ├── scripts/
│   │   └── reprogram_esp32s3.sh               # 一键烧录脚本
│   └── docs/
│       └── ...                                # 固件相关文档
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │                    主机端 VoiceBot 服务                       │
│  └─────────────────────────────────────────────────────────────┘
│
├── dualeye_voicebot/                           # 主机端工程 (git 仓库)
│   │
│   ├── host/                                   # ★ 核心 Python 服务
│   │   ├── .venv/                              # Python 虚拟环境
│   │   ├── requirements.txt                    # 依赖声明
│   │   ├── voicebot_server.py                  # 主服务 (~5300行, asyncio 单进程)
│   │   │                                       #   ├── TCP/UDP 通信
│   │   │                                       #   ├── STT (whisper.cpp HTTP)
│   │   │                                       #   ├── LLM (vLLM OpenAI-compat)
│   │   │                                       #   ├── TTS (Piper HTTP / CosyVoice)
│   │   │                                       #   ├── Streaming STT + LLM prefetch
│   │   │                                       #   ├── Endpoint detection (silence/grace/continuation)
│   │   │                                       #   ├── Tool-call 系统 (volume/weather/...)
│   │   │                                       #   ├── 对话记忆 (deque, token budget)
│   │   │                                       #   └── PC audio 模式 (arecord/aplay)
│   │   │
│   │   ├── reducer_runtime.py                  # Reducer 状态机运行时 (phase-0)
│   │   ├── reducer_state.py                    # Reducer 状态定义
│   │   ├── reducer_types.py                    # Reducer 类型
│   │   ├── ros_bridge_node.py                  # ROS 2 桥接节点 (可选, 预留)
│   │   └── tests/                              # 单元测试
│   │
│   ├── stt_service/                            # STT 独立服务 (whisper.cpp Vulkan)
│   │   ├── README.md
│   │   ├── start_whisper_vulkan_server.sh      # 启动 whisper-server (port 18080)
│   │   ├── stop_whisper_vulkan_server.sh
│   │   └── test_whisper_vulkan_gpu.sh
│   │
│   ├── tts_service/                            # TTS 独立服务 (Piper HTTP)
│   │   ├── README.md
│   │   ├── piper_tts_server.py                 # Piper HTTP 服务 (port 18100)
│   │   ├── qwen_tts_proxy_server.py            # Qwen-TTS 代理 (备选)
│   │   ├── start_piper_tts_service.sh
│   │   ├── stop_piper_tts_service.sh
│   │   └── test_piper_tts_service.sh
│   │
│   ├── tts_cosyvoice2/                         # CosyVoice2 TTS (iGPU/ROCm, 备选)
│   │   ├── CosyVoice/                          # CosyVoice 源码
│   │   ├── .venv-cosyvoice/                    # 独立虚拟环境
│   │   ├── start_cosyvoice2_igpu.sh
│   │   ├── start_funcosyvoice3_igpu.sh
│   │   ├── stop_cosyvoice_igpu.sh
│   │   └── test_cosyvoice_igpu.sh
│   │
│   ├── vllm_qwen3.5_35b_a3b_awq_4bit/         # vLLM LLM 服务 (ROCm dGPU)
│   │   ├── README_35B_A3B_AWQ_4bit.md
│   │   ├── start_qwen3.5_35b_a3b_awq_4bit.sh           # 标准启动 (64k context)
│   │   ├── start_qwen3.5_35b_a3b_awq_4bit_lowlatency.sh # 低延迟启动 (8k context)
│   │   ├── stop_qwen3.5_35b_a3b_awq_4bit.sh
│   │   └── monitor_log_35b_a3b_awq_4bit.sh
│   │
│   ├── models/                                 # 模型文件
│   │   ├── whisper.cpp/                        # ggml-large-v3-q5_0.bin (Vulkan)
│   │   ├── faster-whisper-large-v3/            # faster-whisper (备选)
│   │   ├── faster-whisper-large-v3-turbo/
│   │   ├── faster-whisper-small/
│   │   ├── faster-whisper-tiny/
│   │   ├── Qwen3.5-35B-A3B-AWQ-4bit/          # 主力 LLM 模型
│   │   ├── Qwen3.5-9B/                         # 备选 LLM
│   │   ├── Qwen3.5-2B/                         # 轻量 LLM
│   │   ├── SenseVoiceSmall/                    # FunASR STT 备选
│   │   ├── ParaformerLarge/                    # FunASR STT 备选
│   │   ├── chattts/                            # ChatTTS 模型
│   │   ├── Qwen3-TTS-*/                        # Qwen3-TTS 模型 (4个)
│   │   ├── vosk-model-small-cn-0.22/           # Vosk KWS 中文
│   │   └── vosk-model-small-en-us-0.15/        # Vosk KWS 英文
│   │
│   ├── tools/                                  # 外部工具二进制
│   │   ├── whisper.cpp/                        # whisper-server 编译产物
│   │   └── piper/                              # piper 二进制 + 语音模型
│   │       └── voices/zh_CN-huayan-medium/
│   │
│   ├── scripts/                                # ★ 运维脚本
│   │   ├── runtime_host/                       # 一键服务管理
│   │   │   ├── restart_host_service.sh         # ★ 重启 host 服务
│   │   │   ├── start_host_service.sh
│   │   │   ├── stop_host_service.sh
│   │   │   ├── start_piper_service.sh
│   │   │   ├── stop_piper_service.sh
│   │   │   ├── start_igpu_large_v3_whisper.sh  # whisper Vulkan GPU
│   │   │   ├── stop_igpu_large_v3_whisper.sh
│   │   │   └── start_hotspot_and_check_esp32.sh
│   │   │
│   │   ├── start_mode_vulkan_whispercpp_piper.sh  # 模式: Vulkan STT + Piper TTS
│   │   ├── start_mode_vulkan_pc_audio.sh          # 模式: PC 麦克风/喇叭
│   │   ├── start_mode_stable_whispercpp_piper.sh  # 模式: CPU STT (稳定)
│   │   ├── start_mode_fast_fasterwhisper_small_piper.sh  # 模式: 快速小模型
│   │   │
│   │   ├── serial_monitor_esp32s3.sh           # ESP32 串口监控
│   │   ├── save_current_log_snapshot.sh        # 日志快照
│   │   ├── host_local_voicebot.py              # PC-only 本地测试
│   │   └── run_realworld_stt_selection.sh      # STT 选型测试
│   │
│   ├── data/                                   # 测试数据
│   │   └── stt_benchmark_wavs/                 # STT 测试音频集
│   │
│   ├── asset/                                  # 静态资源
│   │   ├── gpt/                                # system prompt 模板等
│   │   └── tokenizer/                          # tokenizer 配置
│   │
│   ├── archives/                               # 历史归档
│   │   ├── stt_best_20260402_123014/           # STT 最佳配置快照
│   │   └── version_snapshots/                  # 版本代码快照
│   │
│   └── docs/                                   # ★ 项目文档
│       ├── 项目介绍.md
│       ├── host服务参数说明.md
│       ├── start_sequence.md                   # 启动顺序说明
│       ├── Tool-Call语音工具调用机制_2026-04-07.md
│       ├── Memory对话记忆与vLLM延时分析_2026-04-07.md
│       ├── 音频链路与唤醒触发设计_2026-04-01.md
│       ├── 语音管线优化_STT_LLM_TTS流式集成_2026-03-31.md
│       ├── STT_Vulkan_GPU_vs_CPU性能对比_2026-03-31.md
│       ├── 语音Host_reducer改造实施记录_2026-04-06.md
│       └── ...                                 # 其他技术文档
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │                    独立服务 / 外部项目                        │
│  └─────────────────────────────────────────────────────────────┘
│
├── qwen3-tts-rocm/                             # Qwen3-TTS Docker 服务 (ROCm)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── Makefile
│   └── tts_server/                             # TTS FastAPI 服务
│
├── vllm-omni/                                  # vLLM-Omni 分支 (Qwen3-TTS 集成)
│   ├── vllm_omni/                              # 修改后的 vLLM 源码
│   └── ...
│
├── searxng/                                    # SearXNG 搜索引擎 (预留)
│   └── settings.yml
│
├── mcp/                                        # MCP 服务器 (预留)
│   ├── mini_mcp_server.py
│   └── README.md
│
├── claw/                                       # Claw AI Agent 工具 (预留)
│   ├── mcp/
│   ├── rules/
│   └── scripts/
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │                       参考 / 只读                            │
│  └─────────────────────────────────────────────────────────────┘
│
└── ESP32-S3-DualEye-Touch-LCD-1.28-Demo/       # Waveshare 官方 Demo (只读参考)
    ├── Arduino/
    ├── ESP-IDF/
    │   ├── 03_Animated_Eye1/                   # 眼睛动画参考
    │   ├── 06_Music_Player_Touch/              # 音频驱动参考
    │   └── ...
    └── Firmware/
```

---

## 3. 关键架构决策记录

### 3.1 为什么单文件而非多服务

| 考量 | 多节点/微服务 | 单进程 asyncio |
|------|-------------|---------------|
| 延迟 | IPC 开销 (~10-50ms) | **零开销函数调用** |
| 复杂度 | 需要消息序列化/路由 | **直接 await 调用** |
| 部署 | 多进程管理 | **单 PID, 一键重启** |
| 调试 | 分布式日志拼接 | **单文件 log 流** |
| 状态共享 | 需要额外中间件 | **Python 对象直接引用** |

适合当前场景：单设备单用户，延迟敏感。

### 3.2 外部服务进程

虽然 host 是单进程，但 STT/LLM/TTS 引擎各自独立运行：

```
┌──────────────────────────────────────────────────────┐
│                    Host 主机                          │
│                                                      │
│  ┌──────────────────────┐                            │
│  │ voicebot_server.py   │ ← asyncio 管线中枢         │
│  │  port 3000 (TCP)     │                            │
│  │  port 3001 (UDP)     │                            │
│  └───┬──────┬──────┬────┘                            │
│      │      │      │                                 │
│      ▼      ▼      ▼                                 │
│  ┌──────┐ ┌────┐ ┌─────┐                            │
│  │ STT  │ │LLM │ │ TTS │  ← 独立进程/容器            │
│  │:18080│ │:8888│ │:18100│                           │
│  └──────┘ └────┘ └─────┘                            │
│  whisper   vLLM    Piper                             │
│  (Vulkan)  (ROCm)  (CPU)                            │
└──────────────────────────────────────────────────────┘
         ▲
         │ WiFi TCP:3000 + UDP:3001
         │
    ┌────┴────────────────────────┐
    │  ESP32-S3-DualEye           │
    │  (firmware)                 │
    └─────────────────────────────┘
```

### 3.3 启动顺序

```
1. WiFi 热点 (NetworkManager)
2. whisper-server (Vulkan GPU, port 18080)     ← ~30s 首次 shader 编译
3. vLLM (ROCm dGPU, port 8888)                ← ~15s 模型加载
4. Piper TTS (CPU, port 18100)                 ← ~2s
5. voicebot_server.py (port 3000/3001)         ← ~1s
6. ESP32 上电 → WiFi STA 连接 → TCP 握手
```

---

## 4. V1 vs V2 文件对照

### 4.1 V1 规划 → V2 实际映射

| V1 规划文件/模块 | V2 实际位置 | 变更原因 |
|-----------------|-----------|---------|
| `main/uros_node.c` | **已移除** (TCP/UDP Socket) | 延迟和内存考量 |
| `components/eye_animation/` | `firmware/main/eye_animation.c/.h` | 简化为 main 内模块 |
| `components/audio_pipeline/` | `firmware/main/audio_pipeline.c/.h` | 同上 |
| `components/lcd_driver/` | `firmware/main/drivers/lcd_driver.c/.h` | drivers/ 子目录 |
| `components/codec_driver/` | 集成到 `drivers/i2s_audio.c` | 合并简化 |
| `ros2_ws/src/dualeye_host/orchestrator.py` | `host/voicebot_server.py` | 单文件替代多节点 |
| `ros2_ws/src/dualeye_host/stt_node.py` | `stt_service/` + HTTP 调用 | 外部进程 |
| `ros2_ws/src/dualeye_host/llm_node.py` | `vllm_qwen3.5_35b_a3b_awq_4bit/` | vLLM Docker |
| `ros2_ws/src/dualeye_host/tts_node.py` | `tts_service/piper_tts_server.py` | HTTP 服务 |
| `app-colcon.meta` | **已移除** | 不再使用 micro-ROS |

### 4.2 V2 新增模块 (V1 未规划)

| 模块 | 文件 | 说明 |
|------|------|------|
| Streaming STT | `voicebot_server.py` 内 | 录音中实时增量识别 |
| LLM Prefetch | `voicebot_server.py` 内 | STT 完成前预发 LLM 请求 |
| Endpoint Detection | `voicebot_server.py` 内 | 静音检测 + grace window + continuation mode |
| Tool-call | `voicebot_server.py` 内 | `[TOOL:xxx]` prompt-based 工具调度 |
| Weather API | `voicebot_server.py` 内 | wttr.in 天气查询 |
| 对话记忆 | `voicebot_server.py` 内 | deque + token budget sliding window |
| Reducer FSM | `reducer_runtime.py` etc. | 可选的 phase-0 状态观测 |
| Firmware Speech Gate | `audio_pipeline.c` | 320ms 语音能量门控 |
| Follow-up Listen | `state_machine.c` | TTS 播放后自动 10s 免唤醒听 |
| Barge-in | `voicebot_server.py` 内 | 打断正在播放的 TTS |
| TTS CosyVoice2 | `tts_cosyvoice2/` | iGPU ROCm 高质量中文 TTS |
| Qwen3-TTS | `qwen3-tts-rocm/` | Docker 化 TTS 服务 |
| PC Audio 模式 | `voicebot_server.py` 内 | 无 ESP32 时用 PC 麦克风/喇叭 |

---

## 5. 待优化项 (V2.1 方向)

| 项目 | 当前状态 | 改进方向 |
|------|---------|---------|
| voicebot_server.py 体积 | ~5300行单文件 | 按功能拆分模块 (stt.py, tts.py, tools.py, memory.py) |
| 对话记忆持久化 | 纯内存, 重启丢失 | SQLite / JSON 文件落盘 |
| Tool-call 扩展 | volume + weather | 时间/日期、定时器、搜索(SearXNG)、智能家居 |
| Reducer FSM | phase-0 仅观测 | phase-1 实际控制状态转移 |
| ESP32 固件 OTA | 串口烧录 | WiFi OTA 升级 |
| 多设备支持 | 单 ESP32 | session_id 区分多设备 |
| Web 管理面板 | 无 | 简单 HTTP 配置界面 |
