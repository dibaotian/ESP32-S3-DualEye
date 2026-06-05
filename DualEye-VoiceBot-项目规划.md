# ESP32-S3-DualEye 智能语音助手项目规划

> **项目代号**: DualEye-VoiceBot  
> **目标硬件**: ESP32-S3-DualEye-Touch-LCD-1.28 (Waveshare)  
> **开发框架**: ESP-IDF v5.4.1 (Socket 通信) + 主机端 ROS 2  
> **参考工程**: `/home/xilinx/Documents/esp32/wifi_echo_micro_ros`  
> **工程目录**: `/home/xilinx/Documents/ESP32-S3-DualEye/dualeye_voicebot/`  
> **日期**: 2026-03-25  
> **编译状态**: ✅ 已通过 (1.42MB, 53% free)

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [硬件资源分析](#3-硬件资源分析)
4. [软件模块设计](#4-软件模块设计)
5. [ROS 2 通信接口设计](#5-ros-2-通信接口设计)
6. [数据流与交互流程](#6-数据流与交互流程)
7. [任务模型与内存规划](#7-任务模型与内存规划)
8. [开发计划与里程碑](#8-开发计划与里程碑)
9. [工程目录结构](#9-工程目录结构)
10. [关键技术风险与对策](#10-关键技术风险与对策)
11. [主机端 ROS 2 节点设计](#11-主机端-ros-2-节点设计)

---

## 1. 项目概述

### 1.1 目标

构建一个基于 ESP32-S3-DualEye-Touch-LCD-1.28 开发板的**智能语音助手机器人头部**，具备以下核心能力：

| 能力 | 描述 |
|------|------|
| **语音唤醒** | 通过板载双麦克风（ES7210）实现本地离线唤醒词检测（"Hi ESP"） |
| **语音采集与传输** | 唤醒后录制用户语音，通过 WiFi UDP 直传至主机 |
| **语音合成播放** | 接收主机生成的 TTS 音频数据，通过板载喇叭（ES8311）播放 |
| **双屏眼睛动画** | 在双 1.28 寸圆形 LCD 上显示拟人化眼睛动画，根据状态切换表情 |
| **大模型对话** | 主机端接入 LLM（通过VLLM运行），实现自然语言问答 |
| **WiFi 通信** | TCP(JSON 控制) + UDP(裸 PCM 音频)，主机端 ROS Bridge 转发到 ROS Topics |
| **ROS 2 扩展** | 主机端 ROS Bridge 节点将 Socket 消息发布为标准 ROS Topics，供云台/导航等节点使用 |

### 1.2 不包含的功能（当前版本，后续扩展）

- ⏳ 舵机 / 云台 / 电机控制（通过 ROS Bridge 扩展）
- SD 卡音频播放
- 蓝牙功能

### 1.3 用户交互流程

```
用户 ──"Hi ESP"──→ [ESP32 本地唤醒] ──→ 眼睛切换为"倾听"动画
                                         ↓
用户 ──说话──→ [ESP32 录音] ──WiFi/ROS──→ [主机 STT] ──→ [LLM 推理]
                                                              ↓
眼睛切换为"思考"动画 ←── [ESP32 等待]                         ↓
                                                              ↓
[ESP32 播放] ←──WiFi/ROS── [主机 TTS] ←── [LLM 回答文本]
     ↓
眼睛切换为"说话"动画 → 播放结束 → 眼睛恢复"待机"动画
```

---

## 2. 系统架构

### 2.1 整体架构图（Socket + 主机端 ROS Bridge）

```
┌──────────────────────────────────────────────────────────────────┐
│                    Ubuntu 主机 (ROS 2 Humble)                     │
│                                                                    │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ ROS Bridge     │  │ STT Node     │  │ LLM Node            │   │
│  │ (TCP/UDP ↔     │  │ (Whisper)    │  │ (vllm)     │   │
│  │  ROS Topics)   │  └──────┬───────┘  └──────────┬──────────┘   │
│  └───────┬────────┘         │                      │              │
│          │    ROS 2 Topics  │                      │              │
│  ┌───────┴──────────────────┴──────────────────────┴──────────┐   │
│  │                    ROS 2 DDS 通信总线                        │   │
│  └───────┬──────────────────┬──────────────────────┬──────────┘   │
│          │                  │                      │              │
│  ┌───────┴──────┐  ┌───────┴──────┐  ┌─────────────┴──────────┐  │
│  │ TTS Node     │  │ Orchestrator │  │ 云台/导航/其他 Node    │  │
│  │ (edge-tts)   │  │ (对话调度)   │  │ (后续扩展)             │  │
│  └──────────────┘  └──────────────┘  └────────────────────────┘  │
│                                                                    │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ WiFi TCP:3000 + UDP:3001
                           │ (JSON 控制 + 裸 PCM 音频)
                           │
    ┌──────────────────────┴────────────────────────┐
    │         ESP32-S3-DualEye (VoiceBot)            │
    │                                                │
    │  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
    │  │ TCP/UDP  │ │ 语音唤醒 │ │ 音频录制     │   │
    │  │ Socket   │ │ ESP-AFE  │ │ ES7210 I2S   │   │
    │  └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
    │       │            │              │            │
    │  ┌────┴────────────┴──────────────┴─────────┐  │
    │  │          FreeRTOS 任务调度                 │  │
    │  └────┬────────────┬────────────────────────┘  │
    │       │            │                           │
    │  ┌────┴─────┐ ┌────┴─────┐ ┌──────────────┐   │
    │  │ 双屏眼睛 │ │ 状态机   │ │ 音频播放     │   │
    │  │ LVGL     │ │ FSM      │ │ ES8311 I2S   │   │
    │  └──────────┘ └──────────┘ └──────────────┘   │
    │                                                │
    └────────────────────────────────────────────────┘
                           │
              (未来扩展)    │ ROS Topics via Bridge
                           │
    ┌──────────────────────┴────────────────────────┐
    │  云台 ESP32 / 电机驱动 / 传感器等              │
    │  (micro-ROS 或 Socket 均可接入)               │
    └───────────────────────────────────────────────┘
```

### 2.2 通信协议（混合架构）

| 层级 | ESP32 ↔ 主机 | 主机内部 | 说明 |
|------|-------------|---------|------|
| 物理层 | WiFi 2.4GHz STA | localhost | ESP32 连接主机热点 |
| 传输层 | TCP + UDP | DDS (shared memory) | TCP 控制, UDP 音频 |
| 应用层 | JSON + 裸 PCM | ROS 2 Topics | Bridge 节点转换 |

**为什么不在 ESP32 上用 micro-ROS：**

| 对比项 | micro-ROS 在 ESP32 | Socket + 主机 ROS Bridge |
|--------|-------------------|-------------------------|
| 音频延迟 | ~50-100ms/块 (DDS 序列化) | **~1-5ms/块 (裸 UDP)** |
| ESP32 SRAM 占用 | ~80KB | **~5KB** |
| 包大小限制 | 256B (String) | **1400B (UDP MTU)** |
| ROS Topic 可用 | ✅ 直接发布 | ✅ Bridge 节点转发 |
| rviz/rqt 可调试 | ✅ | ✅ |
| 云台/电机扩展 | 另一个 ESP32 跑 micro-ROS | 都通过 Bridge 接入 |
| 开发/编译复杂度 | 高 | **低** |

### 2.3 音频传输方案

**选择：直接 UDP Socket 传输裸 PCM**（延迟最低）

| 方案 | 延迟 | 可靠性 | 选择 |
|------|------|-------|------|
| **裸 UDP Socket** | 1-5ms | 可能丢包 (有序号校验) | ✅ 采用 |
| micro-ROS Topic | 50-100ms | DDS QoS | ❌ 太慢 |
| HTTP POST | 100-500ms | 可靠 | ❌ 太慢 |

**音频分块策略**：
- 上行（ESP32→主机）：录音结束后分块发送，每块 512 bytes，附带序号和总块数
- 下行（主机→ESP32）：TTS 音频分块发送，ESP32 边收边播（流式播放）

---

## 3. 硬件资源分析

### 3.1 板载硬件清单

| 外设 | 芯片/型号 | 接口 | 本项目使用 |
|------|----------|------|----------|
| 双圆形 LCD | GC9A01A ×2 | SPI2 (共享总线) | ✅ 眼睛动画 |
| 双触摸控制器 | CST816 ×2 | I2C0 + I2C1 | ⏳ 预留接口 |
| 音频 DAC/喇叭 | ES8311 | I2S TX + I2C0 | ✅ 语音播放 |
| 音频 ADC/麦克风 | ES7210 (双 MIC) | I2S RX (TDM) + I2C0 | ✅ 语音录制 |
| 功放控制 | PA | GPIO 9 | ✅ 喇叭开关 |
| SD 卡 | SDMMC 1-bit | GPIO 17/18/21 | ❌ 不使用 |
| 电池监测 | ADC | GPIO 0 | ⏳ 预留 |
| WiFi | ESP32-S3 内置 | STA 模式 | ✅ ROS 通信 |

### 3.2 完整 GPIO 分配表

| GPIO | 功能 | 外设 | 占用情况 |
|------|------|------|---------|
| 0 | ADC1_CH0 | 电池电压 | 预留 |
| 2 | I2C1_SCL | 触摸2 | 预留 |
| 3 | I2C1_SDA | 触摸2 | 预留 |
| 4 | TOUCH1_RST | 触摸1 | 预留 |
| 5 | TOUCH1_INT | 触摸1 | 预留 |
| 6 | TOUCH2_RST | 触摸2 | 预留 |
| 7 | TOUCH2_INT | 触摸2 | 预留 |
| 8 | LCD2_RST | 显示屏2 | ✅ 使用 |
| 9 | PA_EN | 功放控制 | ✅ 使用 |
| 10 | I2C0_SCL | 触摸1 + 音频编解码 | ✅ 使用 |
| 11 | I2C0_SDA | 触摸1 + 音频编解码 | ✅ 使用 |
| 12 | I2S_MCLK | 音频主时钟 | ✅ 使用 |
| 13 | I2S_SCLK | 音频位时钟 | ✅ 使用 |
| 14 | I2S_LCLK | 音频帧时钟 | ✅ 使用 |
| 15 | I2S_DSIN | 麦克风输入 (ES7210) | ✅ 使用 |
| 16 | I2S_DOUT | 喇叭输出 (ES8311) | ✅ 使用 |
| 17 | SD_CLK | SD 卡 | ❌ 空闲 |
| 18 | SD_D0 | SD 卡 | ❌ 空闲 |
| 21 | SD_CMD | SD 卡 | ❌ 空闲 |
| 38 | LCD2_CS | 显示屏2 | ✅ 使用 |
| 39 | LCD2_BL | 背光2 (PWM) | ✅ 使用 |
| 40 | SPI_MISO | LCD 共享 | ✅ 使用 |
| 41 | SPI_SCLK | LCD 共享 | ✅ 使用 |
| 42 | SPI_MOSI | LCD 共享 | ✅ 使用 |
| 45 | LCD_DC | LCD 共享 | ✅ 使用 |
| 46 | LCD1_BL | 背光1 (PWM) | ✅ 使用 |
| 47 | LCD1_CS | 显示屏1 | ✅ 使用 |
| 48 | LCD1_RST | 显示屏1 | ✅ 使用 |

---

## 4. 软件模块设计

### 4.1 模块总览

```
┌─────────────────────────────────────────────────────┐
│                    应用层 (Application)                │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ 状态机   │  │ micro-ROS │  │ 音频管道         │  │
│  │ Manager  │  │ Node      │  │ (录制/播放)      │  │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
├───────┼───────────────┼─────────────────┼────────────┤
│       │          驱动层 (Drivers)        │            │
│  ┌────┴─────┐  ┌─────┴─────┐  ┌────────┴─────────┐  │
│  │ 眼睛动画 │  │ WiFi/ROS  │  │ I2S + Codec      │  │
│  │ (LVGL)   │  │ 网络      │  │ (ES8311/ES7210)  │  │
│  └────┬─────┘  └───────────┘  └──────────────────┘  │
│  ┌────┴─────┐                                        │
│  │ LCD 驱动 │                                        │
│  │ GC9A01A  │                                        │
│  └──────────┘                                        │
├──────────────────────────────────────────────────────┤
│                   平台层 (Platform)                    │
│  ESP-IDF (FreeRTOS) + LVGL + ESP-AFE + micro-ROS    │
└──────────────────────────────────────────────────────┘
```

### 4.2 状态机设计

系统核心由一个有限状态机（FSM）驱动：

```
                    ┌──────────┐
          ┌────────→│  IDLE    │←────────────────────┐
          │         │ (待机)   │                      │
          │         └────┬─────┘                      │
          │              │ 检测到唤醒词                  │
          │              ↓                             │
          │         ┌──────────┐                      │
          │         │ WAKEUP   │                      │
          │         │ (唤醒)   │──→ 播放提示音          │
          │         └────┬─────┘                      │
          │              │ 提示音播放完成               │
          │              ↓                             │
          │         ┌──────────┐                      │
     超时(10s)      │ LISTENING│                      │
          │         │ (倾听)   │──→ 录制用户语音       │
          │         └────┬─────┘                      │
          │              │ 检测到语音结束(VAD)          │
          │              ↓                             │
          │         ┌──────────┐                      │
          │         │ THINKING │                      │
          │         │ (思考)   │──→ 等待 LLM 回答      │
          │         └────┬─────┘                      │
          │              │ 收到 TTS 音频               │
          │              ↓                             │
          │         ┌──────────┐                 超时(30s)
          └─────────│ SPEAKING │                      │
                    │ (说话)   │──→ 播放 TTS 音频 ────┘
                    └──────────┘
                         │ 播放完成
                         ↓
                    回到 IDLE
```

**状态与眼睛动画映射：**

| 状态 | 眼睛动画 | 描述 |
|------|---------|------|
| **IDLE** | 慢速随机扫视 + 偶尔眨眼 | 自然待机状态，瞳孔缓慢移动 |
| **WAKEUP** | 眼睛快速睁大 | 被唤醒时的惊喜反应 |
| **LISTENING** | 瞳孔放大 + 缓慢呼吸效果 | 专注倾听，眼睛微微放大 |
| **THINKING** | 眼睛左右移动 + 眨眼加速 | 模拟思考的样子 |
| **SPEAKING** | 眼睛随音量节奏微动 | 说话时的表情 |
| **ERROR** | 眼睛变红/×形 | 出错提示 |

### 4.3 各模块详细设计

#### 4.3.1 眼睛动画模块 (eye_animation)

**职责**：在双屏上渲染拟人化眼睛，支持多种表情和动画效果。

**实现方案**：基于 LVGL 图形库，使用 Canvas 或自定义绘图函数。

**眼睛结构**（每只眼睛由以下层次组成）：
```
┌─────────────────────┐
│   巩膜 (眼白)        │  ← 圆形白色背景
│   ┌───────────────┐  │
│   │  虹膜 (彩色)   │  │  ← 较大圆形，跟随注视方向
│   │  ┌─────────┐  │  │
│   │  │ 瞳孔    │  │  │  ← 黑色圆形，可缩放
│   │  │ (黑色)  │  │  │
│   │  └─────────┘  │  │
│   └───────────────┘  │
│         ● 高光       │  ← 白色小圆，增加立体感
│                      │
│   ═══ 上眼皮 ═══     │  ← 弧形覆盖层，控制"睁眼"程度
│   ═══ 下眼皮 ═══     │  ← 弧形覆盖层
└─────────────────────┘
    240×240 圆形屏幕
```

**关键参数**：
- 巩膜半径：~110px（接近屏幕边缘）
- 虹膜半径：~60px
- 瞳孔半径：~25px（IDLE），~35px（LISTENING 放大）
- 高光：固定在右上方偏移
- 眼皮：通过弧形 mask 层控制开合角度
- 刷新率：目标 30 FPS（LVGL timer 33ms）

**动画定时器**：
- 注视方向：随机目标生成 + 平滑插值（lerp）
- 眨眼：随机间隔 3~8 秒，持续 150ms
- 瞳孔缩放：根据状态平滑过渡

**API**：
```c
void eye_animation_init(void);                    // 初始化双屏 LVGL + 眼睛对象
void eye_set_state(eye_state_t state);            // 切换表情状态
void eye_set_gaze(float x, float y);             // 设置注视方向 (-1.0~1.0)
void eye_set_pupil_scale(float scale);            // 瞳孔缩放 (0.5~1.5)
void eye_set_eyelid(float openness);              // 眼皮开合 (0.0=闭眼, 1.0=全开)
void eye_set_color(uint16_t iris_color);          // 虹膜颜色
void eye_blink(void);                             // 触发一次眨眼
```

#### 4.3.2 音频管道模块 (audio_pipeline)

**职责**：管理 I2S 硬件、录制用户语音、播放 TTS 音频。

**录音流程**：
```
ES7210 (双MIC) → I2S RX (TDM 4ch) → PCM 16kHz/16bit
    → ESP-AFE 前端处理 (降噪/回声消除/波束成形)
    → 唤醒词检测 (ESP-SR)
    → 录音缓冲区 (环形 buffer, 最多 10 秒)
    → 分块通过 ROS Topic 发送至主机
```

**播放流程**：
```
主机 TTS 音频 → ROS Topic 分块接收
    → 播放缓冲区 (环形 buffer)
    → ES8311 DAC → I2S TX → 喇叭
```

**音频格式**：
| 参数 | 值 |
|------|------|
| 采样率 | 16000 Hz |
| 位深 | 16-bit |
| 声道 | 单声道 (mono) |
| 编码 | RAW PCM (ESP32 端) |
| 分块大小 | 512 bytes / 块 |
| 最大录音时长 | 10 秒 (320KB) |

**关键设计**：
- 录音与播放互斥（半双工），避免 I2S 总线冲突和回声问题
- ESP-AFE 仅在 IDLE/LISTENING 状态运行（节省 CPU）
- 播放时停止 AFE 唤醒检测

#### 4.3.3 micro-ROS 节点模块 (uros_node)

**职责**：管理与主机的 ROS 2 通信。

**节点信息**：
- 节点名：`dualeye_voicebot`
- 命名空间：`/dualeye`
- 传输：UDP to Agent (192.168.100.1:8888)

**参考 `wifi_echo_micro_ros` 的设计模式**：
- 预分配静态消息缓冲区（避免堆碎片）
- 非阻塞回调 + FreeRTOS 队列
- 硬件命令解耦（回调只入队，worker 任务执行）
- 心跳定时器（5 秒）

#### 4.3.4 状态管理模块 (state_manager)

**职责**：全局状态机管理，协调各模块行为。

```c
typedef enum {
    STATE_IDLE,         // 待机
    STATE_WAKEUP,       // 刚被唤醒
    STATE_LISTENING,    // 正在录音
    STATE_THINKING,     // 等待 LLM 回答
    STATE_SPEAKING,     // 正在播放 TTS
    STATE_ERROR,        // 错误状态
} system_state_t;

// 状态转移由事件驱动
typedef enum {
    EVT_WAKE_WORD_DETECTED,     // 唤醒词检测到
    EVT_PROMPT_PLAYED,          // 提示音播放完成
    EVT_VAD_END,                // 语音活动结束
    EVT_AUDIO_SENT,             // 录音发送完成
    EVT_TTS_RECEIVED,           // 收到 TTS 音频
    EVT_TTS_DONE,               // TTS 播放完成
    EVT_TIMEOUT,                // 超时
    EVT_ERROR,                  // 错误
} system_event_t;
```

---

## 5. ROS 2 通信接口设计

### 5.1 ESP32 发布的 Topics（ESP32 → 主机）

| Topic | 类型 | 频率 | 说明 |
|-------|------|------|------|
| `/dualeye/heartbeat` | `std_msgs/Int32` | 0.2Hz (5s) | 运行时间(秒)，心跳 |
| `/dualeye/state` | `std_msgs/String` | 事件触发 | 当前状态：`idle`/`listening`/`thinking`/`speaking` |
| `/dualeye/audio_chunk` | `std_msgs/String` | 录音时连续 | Base64 编码的 PCM 音频块，格式：`seq:total:base64data` |
| `/dualeye/wake_event` | `std_msgs/Int32` | 事件触发 | 唤醒事件通知（1=唤醒） |

### 5.2 ESP32 订阅的 Topics（主机 → ESP32）

| Topic | 类型 | 说明 |
|-------|------|------|
| `/dualeye/tts_chunk` | `std_msgs/String` | TTS 音频块：`seq:total:base64data` |
| `/dualeye/tts_control` | `std_msgs/String` | TTS 控制：`start`/`stop`/`cancel` |
| `/dualeye/eye_cmd` | `std_msgs/String` | 眼睛控制指令（见下表） |
| `/dualeye/system_cmd` | `std_msgs/String` | 系统指令：`reboot`/`status`/`volume:N` |

### 5.3 眼睛控制指令格式

通过 `/dualeye/eye_cmd` Topic 控制眼睛表情：

| 指令 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 状态切换 | `state:<name>` | `state:listening` | 切换到预定义动画 |
| 注视方向 | `gaze:<x>,<y>` | `gaze:0.5,-0.3` | x,y 范围 -1.0~1.0 |
| 瞳孔缩放 | `pupil:<scale>` | `pupil:1.3` | 0.5~1.5 |
| 眨眼 | `blink` | `blink` | 触发一次眨眼 |
| 虹膜颜色 | `color:<r>,<g>,<b>` | `color:100,150,255` | RGB 值 |
| 眼皮开合 | `eyelid:<value>` | `eyelid:0.5` | 0.0=闭眼, 1.0=全开 |
| 组合指令 | `multi:cmd1;cmd2` | `multi:state:thinking;color:255,200,100` | 批量执行 |

### 5.4 app-colcon.meta 配置

```json
{
    "names": {
        "rmw_microxrcedds": {
            "cmake-args": [
                "-DRMW_UXRCE_XML_BUFFER_LENGTH=512",
                "-DRMW_UXRCE_TRANSPORT=udp",
                "-DRMW_UXRCE_MAX_NODES=1",
                "-DRMW_UXRCE_MAX_PUBLISHERS=4",
                "-DRMW_UXRCE_MAX_SUBSCRIPTIONS=4",
                "-DRMW_UXRCE_MAX_SERVICES=0",
                "-DRMW_UXRCE_MAX_CLIENTS=0",
                "-DRMW_UXRCE_MAX_HISTORY=16"
            ]
        }
    }
}
```

---

## 6. 数据流与交互流程

### 6.1 完整对话流程（时序）

```
  ESP32                    WiFi/ROS               Ubuntu 主机
    │                         │                        │
    │ [IDLE: 眼睛随机扫视]      │                        │
    │                         │                        │
    │ ◀── 用户说"Hi ESP" ──    │                        │
    │                         │                        │
    │──wake_event(1)─────────→│───wake_event(1)──────→│
    │──state("wakeup")───────→│                        │ Orchestrator 记录
    │                         │                        │
    │ [播放提示音"我在"]        │                        │
    │                         │                        │
    │──state("listening")────→│                        │
    │                         │                        │  Orchestrator
    │ [录音中...]              │                        │  等待音频数据
    │                         │                        │
    │ ◀── 用户说话 ──          │                        │
    │                         │                        │
    │ [VAD 检测到语音结束]      │                        │
    │                         │                        │
    │──audio_chunk(1:N:...)──→│──────────────────────→│ STT Node
    │──audio_chunk(2:N:...)──→│──────────────────────→│ 解码 Base64
    │──    ...                │                        │ 拼接 PCM
    │──audio_chunk(N:N:...)──→│──────────────────────→│ Whisper 转文字
    │                         │                        │    ↓
    │──state("thinking")─────→│                        │ LLM Node
    │                         │                        │ 生成回答
    │ [眼睛"思考"动画]         │                        │    ↓
    │                         │                        │ TTS Node
    │                         │                        │ 文字转语音
    │                         │                        │    ↓
    │                         │←─tts_control("start")──│
    │◀─tts_control("start")──│                        │
    │                         │←─tts_chunk(1:M:...)────│ 分块发送
    │◀─tts_chunk(1:M:...)────│                        │
    │                         │                        │
    │──state("speaking")─────→│                        │
    │ [边收边播放TTS音频]       │                        │
    │                         │                        │
    │◀─tts_chunk(M:M:...)────│←─tts_chunk(M:M:...)────│
    │                         │                        │
    │ [播放完成]               │                        │
    │──state("idle")─────────→│                        │
    │                         │                        │
    │ [IDLE: 眼睛恢复随机扫视]  │                        │
```

### 6.2 音频分块格式

**上行（录音 ESP32→主机）**：

```
Topic: /dualeye/audio_chunk
Format: "<seq>:<total>:<base64_pcm>"
Example: "1:20:SGVsbG8gV29ybGQ..."

其中:
- seq: 当前块序号 (从 1 开始)
- total: 总块数
- base64_pcm: 512 bytes PCM 数据的 Base64 编码 (~684 chars)

完整消息长度: ~700 bytes/块 (在 micro-ROS String 256 byte 限制内需调整)
```

**优化方案**：由于 micro-ROS String 默认缓冲区有限，实际可能需要：
- 增大 `RMW_UXRCE_XML_BUFFER_LENGTH` 至 1024
- 或减小每块 PCM 大小至 256 bytes
- 或使用多个 Topic 并行传输

### 6.3 延迟预算

| 阶段 | 目标延迟 | 说明 |
|------|---------|------|
| 唤醒检测 | < 500ms | ESP-AFE 本地处理 |
| 录音（含 VAD） | 1~10s | 用户说话时间 |
| 音频传输 | < 1s | WiFi UDP 分块传输 |
| STT 转写 | 1~3s | Whisper 本地推理 |
| LLM 推理 | 2~10s | 取决于模型大小和硬件 |
| TTS 合成 | 1~2s | edge-tts 或 piper |
| TTS 播放传输 | 流式 | 边生成边传输边播放 |
| **端到端总延迟** | **5~15s** | 从用户说完到开始播放回答 |

---

## 7. 任务模型与内存规划

### 7.1 FreeRTOS 任务分配

| 优先级 | 任务名 | 栈大小 | CPU 亲和 | 职责 |
|--------|--------|--------|---------|------|
| 1 | `main` | 8192 | ANY | 初始化、WiFi |
| 5 | `uros_task` | 16384 | APP_CPU | micro-ROS 执行器循环 |
| 6 | `audio_worker` | 8192 | PRO_CPU | 音频录制/播放 I2S 操作 |
| 7 | `afe_feed` | 8192 | PRO_CPU | ESP-AFE 音频前端喂数据 |
| 7 | `afe_detect` | 4096 | PRO_CPU | 唤醒词检测结果处理 |
| 4 | `eye_anim` | 4096 | APP_CPU | LVGL 动画刷新 (33ms timer) |
| 3 | `state_mgr` | 4096 | ANY | 状态机事件处理 |

### 7.2 内存预算

ESP32-S3 拥有 512KB SRAM + 8MB PSRAM (板载)：

| 组件 | SRAM 占用 | PSRAM 占用 | 说明 |
|------|----------|-----------|------|
| FreeRTOS 内核 + 栈 | ~60KB | - | 7 个任务的栈 |
| micro-ROS | ~80KB | - | RCL + RMW + XRCE-DDS |
| ESP-AFE + SR 模型 | ~100KB | ~2.9MB | 语音唤醒模型 |
| LVGL + 帧缓冲 | ~50KB | ~230KB | 双屏 240×240 RGB565 × 2 buf |
| I2S DMA 缓冲区 | ~16KB | - | TX + RX DMA |
| 录音缓冲区 | - | ~320KB | 最多 10 秒 PCM |
| 播放缓冲区 | - | ~64KB | 流式播放环形 buffer |
| WiFi 驱动 | ~50KB | - | STA 模式 |
| **总计** | **~356KB** | **~3.5MB** | SRAM 余量 ~156KB |

### 7.3 Flash 分区方案

```
# 分区表 (16MB Flash)
# Name,    Type, SubType,  Offset,   Size
nvs,       data, nvs,      0x9000,   0x6000     # 24KB NVS
phy_init,  data, phy,      0xf000,   0x1000     # 4KB PHY
factory,   app,  factory,  0x10000,  0x300000   # 3MB APP
model,     data, spiffs,   0x310000, 0x2E0000   # 2.9MB SR 模型
storage,   data, fat,      0x5F0000, 0xA10000   # ~10MB 存储 (预留)
```

选择 Partition Scheme：`ESP SR 16M (3MB APP/7MB SPIFFS/2.9MB MODEL)`

---

## 8. 开发计划与里程碑

### Phase 1: 基础框架 (Foundation)

**目标**：搭建工程骨架，验证各硬件驱动独立工作。

| 任务 | 描述 |
|------|------|
| P1.1 | 创建 ESP-IDF 工程，从 Demo 移植 LCD 双屏驱动（GC9A01A） |
| P1.2 | 移植 I2S + ES8311/ES7210 音频驱动 |
| P1.3 | 集成 micro-ROS 组件，实现 WiFi 连接 + 心跳发布 |
| P1.4 | 验证：双屏显示纯色 + 喇叭播放测试音 + ROS 心跳可收 |

### Phase 2: 眼睛动画 (Eye Animation)

**目标**：实现拟人化眼睛渲染和基本动画。

| 任务 | 描述 |
|------|------|
| P2.1 | 集成 LVGL 8.3，配置双屏驱动 |
| P2.2 | 实现眼睛绘制引擎（巩膜/虹膜/瞳孔/高光/眼皮） |
| P2.3 | 实现动画系统（注视/眨眼/瞳孔缩放/表情切换） |
| P2.4 | 实现 ROS 眼睛控制指令订阅 (`/dualeye/eye_cmd`) |
| P2.5 | 验证：通过 ROS 命令控制眼睛表情切换 |

### Phase 3: 语音唤醒与录音 (Voice Wake & Record)

**目标**：实现本地语音唤醒和录音上传。

| 任务 | 描述 |
|------|------|
| P3.1 | 集成 ESP-AFE 音频前端框架 |
| P3.2 | 集成 ESP-SR 唤醒词模型（"Hi ESP"） |
| P3.3 | 实现唤醒检测 → 录音 → VAD 检测语音结束流程 |
| P3.4 | 实现录音 PCM 数据 Base64 编码 + 分块 ROS 发布 |
| P3.5 | 验证：说"Hi ESP"唤醒 → 录音 → 主机端接收并还原为 WAV |

### Phase 4: TTS 播放 (Text-to-Speech Playback)

**目标**：接收主机 TTS 音频并播放。

| 任务 | 描述 |
|------|------|
| P4.1 | 实现 TTS 音频块接收 + Base64 解码 |
| P4.2 | 实现流式播放（环形缓冲区 → I2S TX） |
| P4.3 | 实现录音/播放互斥和状态切换 |
| P4.4 | 验证：主机发送 TTS 音频 → ESP32 喇叭播放 |

### Phase 5: 全链路集成 (End-to-End Integration)

**目标**：完成完整对话流程。

| 任务 | 描述 |
|------|------|
| P5.1 | 实现完整状态机（IDLE → WAKEUP → LISTENING → THINKING → SPEAKING） |
| P5.2 | 眼睛动画与状态同步 |
| P5.3 | 主机端 Orchestrator 节点（调度 STT→LLM→TTS） |
| P5.4 | 端到端测试与优化（延迟、稳定性、断线重连） |

### Phase 6: 主机端 LLM 集成 (LLM Integration)

**目标**：主机端完成 STT + LLM + TTS 全链路。

| 任务 | 描述 |
|------|------|
| P6.1 | STT 节点（Whisper / Vosk） |
| P6.2 | LLM 节点（Ollama 本地 / OpenAI API） |
| P6.3 | TTS 节点（edge-tts / piper） |
| P6.4 | 端到端对话测试 |

---

## 9. 工程目录结构

```
dualeye_voicebot/
├── CMakeLists.txt                         # 顶层 ESP-IDF 构建
├── app-colcon.meta                        # micro-ROS RMW 配置
├── sdkconfig.defaults                     # 默认配置
├── partitions.csv                         # Flash 分区表
├── main/
│   ├── CMakeLists.txt                     # 主组件
│   ├── Kconfig.projbuild                  # WiFi/Agent 可配置项
│   ├── main.c                             # app_main() 入口
│   ├── state_manager.h / .c              # 状态机
│   └── uros_node.h / .c                  # micro-ROS 节点
├── components/
│   ├── eye_animation/                     # 眼睛动画组件
│   │   ├── CMakeLists.txt
│   │   ├── include/eye_animation.h
│   │   ├── eye_animation.c               # 动画逻辑
│   │   └── eye_renderer.c                # 绘制引擎
│   ├── audio_pipeline/                    # 音频管道组件
│   │   ├── CMakeLists.txt
│   │   ├── include/audio_pipeline.h
│   │   ├── audio_record.c                # 录音 (I2S RX + AFE)
│   │   └── audio_playback.c              # 播放 (I2S TX)
│   ├── lcd_driver/                        # LCD 驱动 (从 Demo 移植)
│   │   ├── CMakeLists.txt
│   │   ├── include/lcd_driver.h
│   │   └── gc9a01a.c
│   ├── i2s_driver/                        # I2S 驱动 (从 Demo 移植)
│   │   ├── CMakeLists.txt
│   │   ├── include/i2s_driver.h
│   │   └── i2s_driver.c
│   ├── codec_driver/                      # ES8311 + ES7210 (从 Demo 移植)
│   │   ├── CMakeLists.txt
│   │   ├── include/codec_driver.h
│   │   └── codec_driver.c
│   ├── i2c_driver/                        # I2C 总线 (从 Demo 移植)
│   │   ├── CMakeLists.txt
│   │   ├── include/i2c_driver.h
│   │   └── i2c_driver.c
│   └── micro_ros_espidf_component/        # micro-ROS 预编译库
│       └── ...
└── ros2_ws/                               # 主机端 ROS 2 工作区
    └── src/
        └── dualeye_host/
            ├── package.xml
            ├── setup.py
            ├── dualeye_host/
            │   ├── __init__.py
            │   ├── orchestrator.py        # 对话调度器
            │   ├── stt_node.py            # 语音转文字
            │   ├── llm_node.py            # 大模型接口
            │   └── tts_node.py            # 文字转语音
            └── launch/
                └── voicebot.launch.py     # 一键启动
```

---

## 10. 关键技术风险与对策

### 10.1 内存风险

| 风险 | 影响 | 对策 |
|------|------|------|
| ESP-AFE + LVGL + micro-ROS 同时运行 SRAM 不足 | 系统崩溃 | 帧缓冲和录音 buffer 放 PSRAM；精简 LVGL 配件只用 Canvas |
| SR 模型占用过大 | APP 分区不够 | 使用 `ESP SR 16M` 分区方案，模型放独立分区 |

### 10.2 音频传输风险

| 风险 | 影响 | 对策 |
|------|------|------|
| UDP 丢包导致音频数据不完整 | STT 识别失败 | 添加序号校验；主机端请求重传；增大 `MAX_HISTORY` |
| micro-ROS String 缓冲区不够传大块音频 | 消息截断 | 减小 PCM 块大小(256B)；增大 XML_BUFFER_LENGTH |
| WiFi 延迟抖动 | 播放卡顿 | 播放端维护足够大的预缓冲(2~4 块)再开始播放 |

### 10.3 实时性风险

| 风险 | 影响 | 对策 |
|------|------|------|
| LVGL 渲染阻塞音频 | 声音断续 | LCD 和 Audio 分不同 CPU 核心（PRO_CPU 音频，APP_CPU 显示+ROS） |
| micro-ROS 执行器占 CPU 过高 | 其他任务饿死 | spin_some(20ms) + vTaskDelay(1)；优先级合理分配 |

### 10.4 功能风险

| 风险 | 影响 | 对策 |
|------|------|------|
| 唤醒词误唤醒率高 | 用户体验差 | 调整 AFE 灵敏度参数；添加二次确认机制 |
| 录音与播放同时使用 I2S | 驱动冲突 | 设计为半双工模式，状态机保证互斥 |

---

## 11. 主机端 ROS 2 节点设计

### 11.1 节点架构

```
┌────────────────────────────────────────────────────────┐
│                  voicebot.launch.py                      │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │ micro-ROS    │    │ Orchestrator │    │ STT Node   │ │
│  │ Agent        │    │ Node         │    │ (Whisper)  │ │
│  │ (UDP :8888)  │    │ (对话调度)   │    │            │ │
│  └──────────────┘    └──────┬───────┘    └──────┬─────┘ │
│                             │                    │       │
│                      ┌──────┴────────────────────┴────┐ │
│                      │        ROS 2 DDS               │ │
│                      └──────┬────────────────────┬────┘ │
│                             │                    │       │
│                      ┌──────┴───────┐    ┌───────┴────┐ │
│                      │ LLM Node     │    │ TTS Node   │ │
│                      │ (Ollama/     │    │ (edge-tts/ │ │
│                      │  OpenAI)     │    │  piper)    │ │
│                      └──────────────┘    └────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 11.2 Orchestrator 节点逻辑

```python
class VoiceBotOrchestrator(Node):
    """
    对话调度器：
    1. 监听 /dualeye/wake_event → 准备接收音频
    2. 收集 /dualeye/audio_chunk → 拼接 PCM 数据
    3. 调用 STT 服务 → 获取文本
    4. 调用 LLM 服务 → 获取回答
    5. 调用 TTS 服务 → 获取音频
    6. 分块发布到 /dualeye/tts_chunk
    7. 发布 /dualeye/eye_cmd 控制表情
    """
```

### 11.3 LLM 接入方案

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Ollama 本地** | 隐私好，无网络依赖 | 需要 GPU，推理慢(无GPU) | 有独显的开发机 |
| **OpenAI API** | 响应快，模型强 | 需联网，有费用 | 快速验证 |
| **Ollama + 量化小模型** | 平衡 | CPU推理可接受(3B模型) | 无 GPU 但需离线 |

**推荐初期方案**：先用 OpenAI API 快速验证全链路，后续切换 Ollama 本地部署。

### 11.4 STT/TTS 方案

| 组件 | 推荐方案 | 备选 | 说明 |
|------|---------|------|------|
| STT | **Whisper (faster-whisper)** | Vosk | 本地运行，精度高 |
| TTS | **edge-tts** | piper | 微软在线 TTS，中文效果好 |
| TTS (离线) | **piper** | espeak | 本地运行，低延迟 |

---

## 附录 A: 参考工程对照

从 `wifi_echo_micro_ros` 复用的设计模式：

| 模式 | 原项目实现 | 本项目适配 |
|------|----------|----------|
| WiFi STA + micro-ROS UDP | ✅ 完整实现 | 直接复用 Kconfig + 连接逻辑 |
| 非阻塞回调 + FreeRTOS 队列 | hw_cmd_queue (16 slots) | 改为 audio_cmd_queue + eye_cmd_queue |
| 预分配静态消息缓冲区 | 64-256 bytes char[] | 需增大到 1024 bytes (音频块) |
| 心跳定时器 | 5 秒发布 heartbeat | 直接复用 |
| 多任务优先级模型 | uros(5) > hw_worker(6) | uros(5), audio(6), eye(4), state(3) |
| 启动动画 | LCD/OLED/LED 组合 | 改为双屏眼睛开机动画 |
| app-colcon.meta RMW 配置 | 3 pub + 8 sub | 调整为 4 pub + 4 sub |

## 附录 B: 从 Demo 移植的驱动

从 `ESP32-S3-DualEye-Touch-LCD-1.28-Demo/ESP-IDF/06_Music_Player_Touch/` 移植：

| 驱动 | 源路径 | 移植到 |
|------|--------|--------|
| GC9A01A LCD | `main/LCD_Driver/GC9A01A/` | `components/lcd_driver/` |
| I2C 总线 | `main/I2C_Driver/` | `components/i2c_driver/` |
| I2S 接口 | `main/I2S_Driver/` | `components/i2s_driver/` |
| ES8311 + ES7210 | `main/Audio_Driver/` | `components/codec_driver/` |
| MIC + AFE | `main/MIC_Driver/` | `components/audio_pipeline/` (集成) |
| LCD 背光 | `main/LCD_Driver/LCD_Driver.c` | `components/lcd_driver/` (集成) |
