# ESP32-S3-DualEye 智能语音助手项目

<div align="center">

![Status](https://img.shields.io/badge/status-active-success.svg)
![Version](https://img.shields.io/badge/version-2.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

一个基于 ESP32-S3 的智能语音助手机器人头部，支持本地语音唤醒、实时对话和双屏眼睛动画。

[English](README_EN.md) | 简体中文

</div>

---

## 📖 项目简介

DualEye-VoiceBot 是一个集成了语音交互和视觉表达的智能助手项目，特点包括:

- 🎤 **本地语音唤醒**: 使用 ESP-AFE 实现离线唤醒词检测 ("Hi ESP")
- 🗣️ **实时对话**: whisper.cpp (STT) + vLLM + Qwen3.5 (LLM) + Piper (TTS)
- 👀 **双屏眼睛动画**: 在双 1.28 寸圆形 LCD 上显示拟人化表情
- ⚡ **低延迟通信**: WiFi TCP+UDP Socket，音频延迟 <5ms
- 🛠️ **工具调用**: 天气查询、音量控制等扩展功能
- 💭 **对话记忆**: 上下文管理和多轮对话支持

## 🏗️ 项目结构

```
ESP32-S3-DualEye/
├── PROJECT_REVIEW.md                      # 📊 项目代码审查报告
├── DualEye-VoiceBot-项目规划.md            # 📋 V1 原始规划文档
├── DualEye-VoiceBot-V2-目录结构规划.md     # 📋 V2 架构说明
│
├── DualEye-ESP32S3-Firmware-Pack/         # 🔧 ESP32 固件工程
│   ├── firmware/                          # ESP-IDF 项目
│   │   └── main/                          # 核心代码
│   ├── scripts/                           # 编译/烧录脚本
│   └── docs/                              # 固件文档
│
├── dualeye_voicebot/                      # 🖥️ 主机端服务
│   ├── host/                              # Python 主服务
│   ├── stt_service/                       # STT 服务 (whisper.cpp)
│   ├── tts_service/                       # TTS 服务 (Piper)
│   ├── vllm_qwen3.5_35b_a3b_awq_4bit/    # LLM 服务 (vLLM)
│   ├── models/                            # AI 模型文件
│   ├── scripts/                           # 运维脚本
│   └── docs/                              # 详细技术文档
│
└── ESP32-S3-DualEye-Touch-LCD-1.28-Demo/  # 📚 官方参考 Demo
```

## 🚀 快速开始

### 硬件要求

- **开发板**: ESP32-S3-DualEye-Touch-LCD-1.28 (Waveshare)
- **主机**: Ubuntu/Linux (推荐 16GB+ RAM, AMD GPU 或 iGPU)
- **网络**: WiFi 2.4GHz

### 软件要求

#### ESP32 固件开发
- ESP-IDF v5.4.1
- Python 3.8+
- USB 串口驱动

#### 主机端服务
- Python 3.10+
- ROCm (AMD GPU) 或 Vulkan (iGPU)
- Docker (可选, 用于 TTS 服务)

### 安装步骤

#### 1. ESP32 固件环境配置

```bash
# 安装 ESP-IDF
mkdir -p ~/esp
cd ~/esp
git clone -b v5.4.1 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3

# 设置环境变量
echo 'source ~/esp/esp-idf/export.sh' >> ~/.bashrc
source ~/.bashrc
```

详细说明请参考: [DualEye-ESP32S3-Firmware-Pack/env_setup_manual.md](DualEye-ESP32S3-Firmware-Pack/env_setup_manual.md)

#### 2. 编译并烧录固件

```bash
cd ~/Documents/ESP32-S3-DualEye/DualEye-ESP32S3-Firmware-Pack

# 编译
./scripts/build.sh

# 烧录 (自动检测串口)
./scripts/flash.sh

# 或指定串口
PORT=/dev/ttyACM0 ./scripts/flash.sh

# 监控串口输出
PORT=/dev/ttyACM0 ./scripts/monitor.sh
```

#### 3. 主机端服务配置

```bash
cd ~/Documents/ESP32-S3-DualEye/dualeye_voicebot

# 创建 Python 虚拟环境
cd host
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 4. 启动服务

```bash
cd ~/Documents/ESP32-S3-DualEye/dualeye_voicebot/scripts/runtime_host

# 启动 WiFi 热点并检查 ESP32 连接
./start_hotspot_and_check_esp32.sh

# 启动 STT 服务 (whisper.cpp Vulkan)
./start_igpu_large_v3_whisper.sh

# 启动 TTS 服务 (Piper)
./start_piper_service.sh

# 启动主服务
./start_host_service.sh
```

详细启动流程请参考: [dualeye_voicebot/docs/start_sequence.md](dualeye_voicebot/docs/start_sequence.md)

## 📚 文档导航

### 核心文档
- [📊 项目代码审查报告](PROJECT_REVIEW.md) - 全面的代码质量分析
- [📋 V1 项目规划](DualEye-VoiceBot-项目规划.md) - 原始架构设计
- [📋 V2 目录结构规划](DualEye-VoiceBot-V2-目录结构规划.md) - 架构演化说明

### 固件文档
- [🔧 固件 README](DualEye-ESP32S3-Firmware-Pack/README.md)
- [⚙️ 环境搭建手册](DualEye-ESP32S3-Firmware-Pack/env_setup_manual.md)
- [📈 系统流程图](DualEye-ESP32S3-Firmware-Pack/docs/system_flow.md)

### 主机端文档
- [🖥️ 项目介绍](dualeye_voicebot/docs/项目介绍.md)
- [⚡ 语音管线优化](dualeye_voicebot/docs/语音管线优化_STT_LLM_TTS流式集成_2026-03-31.md)
- [🛠️ Tool-Call 机制](dualeye_voicebot/docs/Tool-Call语音工具调用机制_2026-04-07.md)
- [💭 对话记忆与延时分析](dualeye_voicebot/docs/Memory对话记忆与vLLM延时分析_2026-04-07.md)
- [📊 STT 模型选型测试](dualeye_voicebot/docs/STT模型选型深度测试_2026-03-28.md)

## 🎯 核心特性

### 语音交互流程

```
用户说 "Hi ESP" 
    ↓
[ESP32 本地唤醒] → 眼睛切换为 "倾听" 动画
    ↓
[录音并发送] → WiFi UDP 传输 PCM 音频
    ↓
[主机 STT] → whisper.cpp 实时转文字
    ↓
[LLM 推理] → Qwen3.5-35B-A3B 生成回答
    ↓
[TTS 合成] → Piper 文字转语音
    ↓
[ESP32 播放] → 喇叭输出 + 眼睛 "说话" 动画
    ↓
[Follow-up Listen] → 10s 免唤醒继续对话
```

### 架构亮点

- **低延迟通信**: 放弃 micro-ROS，改用 TCP+UDP Socket，延迟降低 50-100ms
- **单进程 asyncio**: 主机端避免 IPC 开销，延迟降低 10-50ms
- **流式处理**: STT/LLM/TTS 流式集成，边识别边推理边合成
- **LLM Prefetch**: STT 完成前预发 LLM 请求，减少等待时间
- **Endpoint Detection**: 智能检测语音结束，支持连续说话
- **Barge-in**: 可打断正在播放的回答

## 🛠️ 技术栈

### ESP32 固件
- **框架**: ESP-IDF v5.4.1
- **语音**: ESP-AFE (唤醒) + ES7210 (ADC) + ES8311 (DAC)
- **显示**: LVGL 8.3 + GC9A01A (双屏)
- **通信**: WiFi STA + TCP/UDP Socket

### 主机端
- **语言**: Python 3.10+ (asyncio)
- **STT**: whisper.cpp (Vulkan GPU加速)
- **LLM**: vLLM + Qwen3.5-35B-A3B-AWQ (ROCm)
- **TTS**: Piper (CPU) / CosyVoice2 (GPU, 可选)

## 📈 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 唤醒检测延迟 | <500ms | ~300ms |
| 音频传输延迟 | <1s | ~200ms |
| STT 转写延迟 | 1-3s | ~1.5s |
| LLM 推理延迟 | 2-10s | ~3-5s |
| TTS 合成延迟 | 1-2s | ~1s |
| **端到端总延迟** | **5-15s** | **~6-8s** |

## 🤝 贡献指南

欢迎贡献! 请查看 [CONTRIBUTING.md](CONTRIBUTING.md) (待添加)

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [ESP-IDF](https://github.com/espressif/esp-idf) - ESP32 开发框架
- [LVGL](https://github.com/lvgl/lvgl) - 嵌入式图形库
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - 高效 STT 引擎
- [vLLM](https://github.com/vllm-project/vllm) - 高性能 LLM 推理引擎
- [Qwen](https://github.com/QwenLM/Qwen) - 强大的开源大模型
- [Piper](https://github.com/rhasspy/piper) - 快速 TTS 引擎

## 📞 联系方式

- **问题反馈**: [GitHub Issues](https://github.com/yourusername/ESP32-S3-DualEye/issues)
- **邮件**: xilinx@local

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star! ⭐**

Made with ❤️ by xilinx

</div>
