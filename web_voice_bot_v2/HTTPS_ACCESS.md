# HTTPS 访问指南 - 麦克风权限

## ✅ HTTPS 服务器已启动！

浏览器的 WebAudio API 需要 **HTTPS** 或 **localhost** 才能访问麦克风。

---

## 🌐 访问地址

### HTTPS 地址（推荐）

```
https://127.0.0.1:8888
https://localhost:8888
```

**重要**: 使用 `https://` 而不是 `http://`

---

## ⚠️ 证书警告处理

由于使用自签名证书，浏览器会显示安全警告。这是**正常的**，请按以下步骤操作：

### Chrome/Edge

1. 访问 `https://127.0.0.1:8888`
2. 看到 "您的连接不是私密连接" 警告
3. 点击 **"高级"** 
4. 点击 **"继续前往 127.0.0.1（不安全）"**
5. 页面正常加载

### Firefox

1. 访问 `https://127.0.0.1:8888`
2. 看到 "警告：潜在的安全风险"
3. 点击 **"高级"**
4. 点击 **"接受风险并继续"**
5. 页面正常加载

### Safari

1. 访问 `https://127.0.0.1:8888`
2. 看到 "此连接不是私密连接"
3. 点击 **"显示详细信息"**
4. 点击 **"访问此网站"**
5. 确认继续

---

## 🎤 麦克风权限

页面加载后：

1. 点击 **"开始对话"** 按钮
2. 浏览器会弹出麦克风权限请求
3. 点击 **"允许"** 或 **"Allow"**
4. 开始说话测试

### 如果没有权限弹窗

**检查浏览器设置：**

#### Chrome/Edge
1. 点击地址栏左侧的 🔒 或 ℹ️ 图标
2. 找到 "麦克风" 设置
3. 改为 "允许"
4. 刷新页面

#### Firefox
1. 点击地址栏左侧的 🔒 图标
2. 点击 "连接安全"
3. 点击 "更多信息"
4. 找到 "麦克风" 权限
5. 改为 "允许"
6. 刷新页面

---

## 🔧 故障排除

### 问题1: "连接不安全" 无法绕过

**解决方案**: 在Chrome中输入 `chrome://flags/#allow-insecure-localhost`，设置为 **Enabled**

### 问题2: 麦克风仍然无法访问

**检查清单**:
- ✅ 确认使用 `https://`（不是 `http://`）
- ✅ 接受了证书警告
- ✅ 允许了麦克风权限
- ✅ 系统麦克风正常工作
- ✅ 其他应用没有占用麦克风

**系统麦克风测试**:
```bash
# Linux
arecord -l  # 列出麦克风设备

# 测试录音
arecord -d 3 test.wav
aplay test.wav
```

### 问题3: 页面无法加载

**检查服务器状态**:
```bash
# 查看进程
ps aux | grep "python.*app.py"

# 查看日志
tail -f voice_bot.log

# 重启服务器
pkill -f "python.*app.py"
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
./start_https.sh
```

---

## 📱 局域网访问

如果从其他设备（手机/平板）访问：

### 1. 生成匹配IP的证书

```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2

# 停止服务器
pkill -f "python.*app.py"

# 重新生成证书（包含局域网IP）
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout key.pem -out cert.pem -days 365 \
  -subj "/CN=10.161.176.132" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.161.176.132"

# 重启服务器
venv/bin/python app.py --port 8888 --ssl-cert cert.pem --ssl-key key.pem &
```

### 2. 访问地址

```
https://10.161.176.132:8888
```

### 3. 接受证书

在移动设备浏览器中接受证书警告（步骤同上）

---

## 🚀 快速启动脚本

创建快速启动脚本：

```bash
cat > start_https.sh << 'SCRIPT'
#!/bin/bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2

# 停止旧进程
pkill -f "python.*app.py" 2>/dev/null

# 等待停止
sleep 2

# 启动HTTPS服务器
nohup venv/bin/python app.py --port 8888 \
  --ssl-cert cert.pem --ssl-key key.pem \
  > https_server.log 2>&1 &

# 等待启动
sleep 3

echo "====================================="
echo "DualEye Voice Bot - HTTPS Server"
echo "====================================="
echo ""
echo "✅ Server started"
echo ""
echo "📍 Access URL:"
echo "   https://127.0.0.1:8888"
echo "   https://localhost:8888"
echo ""
echo "⚠️  Accept certificate warning in browser"
echo "🎤 Allow microphone permission"
echo ""
echo "📝 View logs: tail -f voice_bot.log"
echo "🛑 Stop: pkill -f 'python.*app.py'"
echo ""
SCRIPT

chmod +x start_https.sh
```

使用：
```bash
./start_https.sh
```

---

## 📊 当前状态

- ✅ HTTPS服务器运行在 **https://127.0.0.1:8888**
- ✅ SSL证书已生成（自签名）
- ✅ 所有后端服务健康
- ✅ 准备接受语音输入

---

## 🎯 下一步

1. **打开浏览器**
2. **访问**: `https://127.0.0.1:8888`
3. **接受证书警告**
4. **点击"开始对话"**
5. **允许麦克风权限**
6. **开始说话！**

---

## 💡 提示

- 第一次访问需要接受证书和允许麦克风
- 之后访问会记住权限设置
- 如果更换浏览器需要重新授权
- HTTPS比HTTP稍慢一点点（SSL加密开销）

---

**现在可以访问**: `https://127.0.0.1:8888` 并使用麦克风了！
