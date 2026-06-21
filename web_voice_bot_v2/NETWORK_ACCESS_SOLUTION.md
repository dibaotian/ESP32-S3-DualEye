# 局域网访问解决方案

## 问题分析

- ✅ 服务器正在运行
- ✅ 端口8888监听 0.0.0.0（所有接口）
- ❌ 局域网IP访问超时（SSL握手问题）

**原因**：Flask开发服务器的SSL实现在处理远程连接时性能较差，容易超时。

---

## 🎯 推荐方案

### 方案1: 本地使用（推荐） ⭐⭐⭐⭐⭐

**最简单稳定的方案**：在运行服务器的机器上直接使用

```
https://127.0.0.1:8888
https://localhost:8888
```

**优点**：
- ✅ 无需额外配置
- ✅ SSL握手快速
- ✅ 麦克风权限正常工作
- ✅ 性能最佳

---

### 方案2: HTTP局域网访问 ⭐⭐⭐

**限制**：麦克风在远程设备上无法使用（需要HTTPS）

#### 2.1 启动HTTP服务器

```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2

# 停止HTTPS服务器
pkill -f "python.*app.py"

# 启动HTTP服务器（不要SSL参数）
nohup venv/bin/python app.py --port 8888 > http_server.log 2>&1 &
```

#### 2.2 访问地址

```
http://10.161.176.132:8888  # 从其他设备访问
```

**注意**：
- ✅ 可以查看界面
- ✅ 可以看到聊天记录
- ❌ **无法使用麦克风**（浏览器限制）
- 适合演示或查看，不适合实际使用

---

### 方案3: 使用Nginx反向代理 + HTTPS ⭐⭐⭐⭐

**适合生产环境**，需要一些配置

#### 3.1 安装Nginx

```bash
sudo apt update
sudo apt install nginx -y
```

#### 3.2 配置Nginx

```bash
sudo tee /etc/nginx/sites-available/voicebot << 'EOF'
server {
    listen 443 ssl;
    server_name 10.161.176.132;

    ssl_certificate /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/cert.pem;
    ssl_certificate_key /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket超时设置
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

# 启用配置
sudo ln -sf /etc/nginx/sites-available/voicebot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 3.3 调整服务器

```bash
# 停止HTTPS服务器
pkill -f "python.*app.py"

# 启动HTTP服务器（Nginx会处理HTTPS）
venv/bin/python app.py --host 127.0.0.1 --port 8888 &
```

#### 3.4 访问

```
https://10.161.176.132  # 默认443端口
```

---

### 方案4: SSH隧道转发 ⭐⭐⭐⭐

**从其他机器通过SSH安全访问**

在客户端机器上运行：

```bash
# 建立SSH隧道
ssh -L 8888:localhost:8888 xilinx@10.161.176.132

# 然后在客户端浏览器访问
https://localhost:8888
```

**优点**：
- ✅ 安全
- ✅ 不需要修改服务器配置
- ✅ 麦克风正常工作

---

### 方案5: 移动热点共享 ⭐⭐

如果是要在手机上测试：

1. 在服务器机器上开启WiFi热点
2. 手机连接该热点
3. 访问 `https://192.168.100.1:8888`（WiFi热点IP）

---

## 🔧 当前建议

### 立即可用（本地）

```bash
# 确保HTTPS服务器运行
ps aux | grep "python.*app.py"

# 在服务器机器的浏览器访问
https://127.0.0.1:8888
```

### 如果确实需要远程访问

**选择方案3（Nginx）**，执行以下步骤：

```bash
# 1. 安装Nginx
sudo apt install nginx -y

# 2. 配置（见上方）
# 3. 停止Flask HTTPS
pkill -f "python.*app.py"

# 4. 启动Flask HTTP（只监听本地）
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
venv/bin/python app.py --host 127.0.0.1 --port 8888 &

# 5. 访问
# https://10.161.176.132
```

---

## 📝 快速测试脚本

```bash
cat > test_network_access.sh << 'SCRIPT'
#!/bin/bash

echo "===== Network Access Test ====="
echo ""

# 获取所有IP
echo "Available IPs:"
ip addr show | grep "inet " | grep -v 127.0.0.1 | awk '{print "  " $2}'

echo ""
echo "Testing local access..."
curl -k -s -o /dev/null -w "  https://127.0.0.1:8888 - %{http_code}\n" https://127.0.0.1:8888

echo ""
echo "Testing LAN access (may timeout)..."
timeout 3 curl -k -s -o /dev/null -w "  https://10.161.176.132:8888 - %{http_code}\n" https://10.161.176.132:8888 || echo "  https://10.161.176.132:8888 - Timeout"

echo ""
echo "Recommendation:"
echo "  - Local use: https://127.0.0.1:8888 ✅"
echo "  - Remote use: Setup Nginx reverse proxy"
SCRIPT

chmod +x test_network_access.sh
./test_network_access.sh
```

---

## 🎯 最终建议

**对于当前测试**：

1. **在本机使用** `https://127.0.0.1:8888` ✅
   - 最稳定
   - 性能最好
   - 无需额外配置

2. **如需远程演示**：
   - 方案A: 安装Nginx（生产级）
   - 方案B: SSH隧道（临时使用）
   - 方案C: HTTP模式（仅查看界面）

---

## 当前状态

- ✅ HTTPS服务器运行正常
- ✅ 本地访问完美工作
- ⚠️ 远程访问需要额外配置
- 推荐：**本地使用或配置Nginx**

---

**现在建议**：在服务器本机浏览器访问 `https://127.0.0.1:8888` 进行完整测试！
