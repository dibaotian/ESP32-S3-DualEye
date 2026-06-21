# Docker 快速启动指南

## 🚀 一键部署

```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
./deploy_docker.sh
```

---

## 📍 访问地址

部署成功后，从**任何设备**访问：

### 本机
```
https://localhost
https://127.0.0.1
```

### 局域网（手机/平板/其他电脑）
```
https://10.161.176.132
```

**HTTP会自动重定向到HTTPS！**

---

## ⚡ 手动启动

如果自动脚本失败，手动执行：

### 1. 构建镜像
```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
docker compose build
```

### 2. 启动服务
```bash
docker compose up -d
```

### 3. 查看日志
```bash
docker compose logs -f
```

### 4. 检查状态
```bash
docker compose ps
```

---

## 🎯 使用步骤

1. **打开浏览器**（任何设备）
2. **访问**: `https://10.161.176.132`
3. **接受证书警告**（自签名证书）
   - 点击 "高级"
   - 点击 "继续访问"
4. **点击"开始对话"**
5. **允许麦克风权限**
6. **开始说话！**

---

## 🛠️ 常用命令

### 查看日志
```bash
# 所有服务
docker compose logs -f

# Voice Bot
docker logs -f dualeye-voicebot

# Nginx
docker logs -f dualeye-nginx
```

### 重启服务
```bash
docker compose restart
```

### 停止服务
```bash
docker compose down
```

### 重新部署
```bash
./deploy_docker.sh
```

---

## ✅ 优势

✅ **远程访问稳定** - Nginx专业HTTPS处理  
✅ **自动重启** - 容器崩溃自动恢复  
✅ **一键部署** - 无需手动配置  
✅ **隔离环境** - 不影响系统  
✅ **生产就绪** - 可直接使用  

---

## 📊 架构

```
客户端浏览器
    ↓
  :443 (HTTPS)
    ↓
Nginx容器 (SSL终止)
    ↓
  :8888 (HTTP)
    ↓
Voice Bot容器
    ↓
ASR Service (:8101)
vLLM Service (:8102)
```

---

## 🐛 故障排除

### 问题: 容器启动失败

```bash
# 查看详细日志
docker compose logs

# 检查端口
netstat -tuln | grep -E "443|80|8888"

# 确保旧进程已停止
pkill -f "python.*app.py"
docker compose down
```

### 问题: 无法访问

```bash
# 检查容器状态
docker compose ps

# 测试本地访问
curl -k https://localhost

# 查看Nginx日志
docker logs dualeye-nginx
```

### 问题: 后端服务连接失败

**确保ASR和vLLM服务运行**:
```bash
curl http://localhost:8101/health
curl http://localhost:8102/health
```

---

## 🎉 完成

Docker部署后，**远程Web访问问题已完全解决**！

现在可以从任何设备访问 `https://10.161.176.132` 🚀
