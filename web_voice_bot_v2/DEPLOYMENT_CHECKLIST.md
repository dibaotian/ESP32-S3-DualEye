# 部署检查清单

在启动 DualEye Voice Bot v2 之前，请按照此清单逐项检查。

## ✅ 环境准备

- [ ] Python 3.10 或更高版本已安装
  ```bash
  python3 --version
  ```

- [ ] NVIDIA GPU 驱动已安装 (可选，用于加速)
  ```bash
  nvidia-smi
  ```

- [ ] 网络连接正常 (用于下载模型)

## ✅ 依赖服务

### ASR Service (端口 8101)

- [ ] ASR Service 已启动
  ```bash
  curl http://localhost:8101/health
  ```
  
  预期输出: `{"status": "healthy"}` 或类似信息

- [ ] 测试 ASR 端点
  ```bash
  cd ../ASR_Service
  python test_asr_service.py --test health
  ```

### vLLM Service (端口 8102)

- [ ] vLLM Service 已启动
  ```bash
  curl http://localhost:8102/health
  ```
  
  预期输出: `{"status": "healthy"}` 或类似信息

- [ ] 测试 LLM 端点
  ```bash
  cd ../vllm_Qwen3.5-35B-A3B-W4A16_Service
  python benchmark_llm.py --runs 1
  ```

## ✅ Voice Bot 安装

- [ ] 克隆/下载项目到本地
  ```bash
  cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
  ```

- [ ] 运行安装脚本
  ```bash
  ./install.sh
  ```
  
  检查输出是否有错误

- [ ] 激活虚拟环境
  ```bash
  source venv/bin/activate
  ```

- [ ] 验证 Python 包
  ```bash
  pip list | grep -E "flask|torch|melo|httpx"
  ```

## ✅ 组件测试

- [ ] 运行组件测试脚本
  ```bash
  python test_components.py
  ```

- [ ] 确认所有测试通过
  - ✓ PASS: PyTorch
  - ✓ PASS: Flask-SocketIO
  - ✓ PASS: Silero VAD
  - ✓ PASS: MeloTTS
  - ✓ PASS: ASR Service
  - ✓ PASS: vLLM Service

## ✅ SSL 证书 (可选但推荐)

- [ ] 生成自签名证书 (如果需要 HTTPS)
  ```bash
  openssl req -x509 -newkey rsa:4096 -nodes \
    -out cert.pem -keyout key.pem -days 365
  ```

- [ ] 证书文件已生成
  ```bash
  ls -lh cert.pem key.pem
  ```

## ✅ 启动服务器

### HTTP 模式 (快速测试)

- [ ] 启动服务器
  ```bash
  python app.py --host 0.0.0.0 --port 8888
  ```

- [ ] 检查输出日志
  - 应看到 "Pipeline initialized successfully"
  - 应看到 "Running on http://0.0.0.0:8888"

### HTTPS 模式 (推荐)

- [ ] 使用 SSL 启动
  ```bash
  python app.py --ssl-cert cert.pem --ssl-key key.pem
  ```

- [ ] 检查输出日志
  - 应看到 "SSL enabled"

## ✅ 前端访问

- [ ] 浏览器打开 URL
  - HTTP: http://localhost:8888
  - HTTPS: https://localhost:8888

- [ ] 页面正常加载
  - 看到 "DualEye Voice Bot" 标题
  - 看到 "开始对话" 按钮
  - 状态显示 "已连接"

- [ ] 测试麦克风权限
  - 点击 "开始对话"
  - 浏览器提示麦克风权限
  - 点击 "允许"

## ✅ 功能测试

- [ ] 语音识别测试
  - 说话后看到蓝色气泡 (用户消息)
  - 文本正确识别

- [ ] LLM 生成测试
  - 看到橙色气泡 (AI 回复)
  - 回复内容合理

- [ ] 语音合成测试
  - 听到 AI 语音播放
  - 音质清晰无卡顿

- [ ] 对话连续性
  - 可以连续多轮对话
  - 上下文保持正确

## ✅ 性能检查

- [ ] 检查延迟
  - 从说话结束到听到回复: <3 秒
  - 理想延迟: <1.5 秒

- [ ] 检查资源占用
  ```bash
  # CPU 使用率
  top -p $(pgrep -f "python app.py")
  
  # GPU 使用率 (如果有)
  nvidia-smi
  ```

- [ ] 检查日志无异常
  ```bash
  tail -f voice_bot.log
  ```

## ✅ 常见问题解决

### 问题: 麦克风无法访问
- [ ] 确认使用 HTTPS 或 localhost
- [ ] 检查浏览器权限设置
- [ ] 尝试其他浏览器 (Chrome/Edge 推荐)

### 问题: ASR/LLM 连接失败
- [ ] 检查服务是否运行
  ```bash
  netstat -tuln | grep -E "8101|8102"
  ```
- [ ] 检查防火墙设置
- [ ] 查看服务日志

### 问题: TTS 无声音
- [ ] 检查浏览器音频权限
- [ ] 检查系统音量
- [ ] 打开浏览器控制台查看错误

### 问题: GPU OOM
- [ ] 减小 batch size
- [ ] 使用 CPU 模式
  ```python
  # 在 app.py 中修改
  tts = TTSHandler(..., device='cpu')
  ```

## ✅ 生产部署 (可选)

- [ ] 使用进程管理器 (如 systemd, supervisor)
- [ ] 配置反向代理 (如 Nginx)
- [ ] 设置日志轮转
- [ ] 配置监控告警
- [ ] 备份配置文件

## ✅ 完成

全部检查通过后，系统即可正常使用！

如有问题，请查看:
- `voice_bot.log` - 应用日志
- `README.md` - 详细文档
- `QUICKSTART.md` - 快速指南

享受超低延迟的语音对话体验！🎉
