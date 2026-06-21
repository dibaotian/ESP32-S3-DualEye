# 连接问题排查指南

## 问题：ERR_CONNECTION_REFUSED

### ✅ 当前状态确认

服务器**正在运行**：
- ✅ 进程存在 (PID: 2540718)
- ✅ 端口8888监听中
- ✅ curl测试成功
- ✅ 日志正常

### 🔍 原因分析

**最可能的原因**：

1. **IPv6冲突** - 浏览器尝试IPv6 (::1) 连接，但服务器只监听IPv4
2. **浏览器缓存** - 旧的连接信息被缓存
3. **DNS解析** - localhost解析到IPv6地址

### 🛠️ 解决方案

#### 方案1: 使用IPv4地址 (推荐) ⭐⭐⭐

**直接使用IPv4地址，绕过IPv6问题：**

```
http://127.0.0.1:8888
```

**不要使用**：
- ❌ `http://localhost:8888` (可能解析到IPv6)
- ❌ `http://[::1]:8888` (IPv6不可用)

#### 方案2: 清除浏览器缓存

**Chrome/Edge:**
1. 按 `Ctrl+Shift+Delete`
2. 选择 "缓存的图片和文件"
3. 清除
4. 重新访问 `http://127.0.0.1:8888`

**或使用隐私模式:**
- `Ctrl+Shift+N` (Chrome)
- `Ctrl+Shift+P` (Firefox)

#### 方案3: 禁用IPv6 (临时)

```bash
# 浏览器地址栏输入
chrome://flags/#enable-network-service-in-process

# 设置为 Disabled
```

#### 方案4: 重启服务器 (绑定IPv4)

```bash
# 停止当前服务器
pkill -f "python.*app.py"

# 使用IPv4地址启动
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
venv/bin/python app.py --host 127.0.0.1 --port 8888 &

# 等待启动
sleep 3

# 测试
curl http://127.0.0.1:8888
```

#### 方案5: 使用其他端口

如果8888端口有问题，换个端口：

```bash
# 停止当前服务器
pkill -f "python.*app.py"

# 使用9999端口
venv/bin/python app.py --host 0.0.0.0 --port 9999 &

# 访问
http://127.0.0.1:9999
```

### 🧪 诊断命令

运行这些命令检查问题：

```bash
# 1. 检查IPv6是否启用
ip -6 addr show | grep ::1

# 2. 测试IPv4连接
curl -4 http://localhost:8888

# 3. 测试IPv6连接  
curl -6 http://localhost:8888

# 4. 检查服务器监听地址
netstat -tuln | grep 8888

# 5. 查看DNS解析
getent hosts localhost
```

### 📝 快速验证

```bash
# 运行这个脚本一键检查
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2

cat > check_connection.sh << 'SCRIPT'
#!/bin/bash
echo "===== Connection Diagnostic ====="
echo ""

# 1. Check process
echo "1. Server Process:"
ps aux | grep "python.*app.py" | grep -v grep || echo "  ❌ Server not running"

# 2. Check port
echo ""
echo "2. Port Listening:"
lsof -i :8888 2>/dev/null || echo "  ❌ Port 8888 not listening"

# 3. Test IPv4
echo ""
echo "3. IPv4 Connection (127.0.0.1):"
curl -4 -s -o /dev/null -w "  Status: %{http_code}\n" http://127.0.0.1:8888 2>/dev/null

# 4. Test localhost
echo ""
echo "4. Localhost Connection:"
curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8888 2>/dev/null

# 5. Check localhost resolution
echo ""
echo "5. Localhost DNS:"
getent hosts localhost | head -2

echo ""
echo "===== Recommendation ====="
echo "Use: http://127.0.0.1:8888"
SCRIPT

chmod +x check_connection.sh
./check_connection.sh
```

### 🎯 最佳实践

**推荐访问方式（按优先级）：**

1. ✅ `http://127.0.0.1:8888` - 最稳定
2. ✅ `http://10.161.176.132:8888` - 局域网访问
3. ⚠️ `http://localhost:8888` - 可能有IPv6问题

### 🌐 浏览器兼容性

| 浏览器 | IPv4 | IPv6 | 推荐 |
|--------|------|------|------|
| Chrome | ✅ | ⚠️ | 使用127.0.0.1 |
| Firefox | ✅ | ⚠️ | 使用127.0.0.1 |
| Edge | ✅ | ⚠️ | 使用127.0.0.1 |
| Safari | ✅ | ⚠️ | 使用127.0.0.1 |

### 📱 移动设备访问

如果从手机/平板访问：

```
http://10.161.176.132:8888
```

**注意**：需要HTTPS才能使用麦克风，参考 BROWSER_ACCESS_GUIDE.md

### 🔥 终极解决方案

如果以上都不行，重新启动并绑定所有接口：

```bash
# 完全停止
pkill -9 -f "python.*app.py"
sleep 2

# 清理日志
> voice_bot.log

# 重新启动
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
nohup venv/bin/python app.py --host 0.0.0.0 --port 8888 > server.log 2>&1 &

# 等待启动
sleep 5

# 测试所有地址
echo "Testing connections..."
curl -s -o /dev/null -w "127.0.0.1:8888 - %{http_code}\n" http://127.0.0.1:8888
curl -s -o /dev/null -w "localhost:8888 - %{http_code}\n" http://localhost:8888
curl -s -o /dev/null -w "10.161.176.132:8888 - %{http_code}\n" http://10.161.176.132:8888

# 查看日志
tail -20 voice_bot.log
```

### ❓ 仍然无法连接？

提供以下信息以便诊断：

```bash
# 收集诊断信息
cat > diagnostic_info.txt << EOF
System Info:
$(uname -a)

Browser: [请填写浏览器类型和版本]

Process Status:
$(ps aux | grep "python.*app.py" | grep -v grep)

Port Status:
$(lsof -i :8888)

IPv6 Status:
$(ip -6 addr show | grep ::1)

Localhost Resolution:
$(getent hosts localhost)

Curl Test:
$(curl -v http://127.0.0.1:8888 2>&1 | head -20)

Recent Logs:
$(tail -30 voice_bot.log)
EOF

cat diagnostic_info.txt
```

---

## ✅ 当前推荐

**立即尝试这个地址：**

```
http://127.0.0.1:8888
```

如果还是不行，运行诊断脚本：
```bash
./check_connection.sh
```
