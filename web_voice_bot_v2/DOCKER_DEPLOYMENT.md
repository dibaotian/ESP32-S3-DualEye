# Docker 部署指南

## ✨ 优势

使用Docker + Nginx部署的好处：

- ✅ **远程访问稳定** - Nginx专业处理HTTPS
- ✅ **自动重启** - 容器崩溃自动恢复
- ✅ **易于部署** - 一键启动
- ✅ **隔离环境** - 不影响系统环境
- ✅ **WebSocket完美支持** - Nginx优化配置

---

## 🚀 快速部署

### 一键部署

```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
./deploy_docker.sh
```

**就这么简单！** 🎉

---

## 📋 详细步骤

### 1. 前置要求

确保以下服务运行：
- ✅ ASR Service (端口 8101)
- ✅ vLLM Service (端口 8102)
- ✅ Docker & Docker Compose

### 2. 部署架构

```
Internet/LAN
    ↓
  :443 (HTTPS)
    ↓
[Nginx容器] ← SSL/TLS终止
    ↓
  :8888 (HTTP)
    ↓
[Voice Bot容器]
    ↓
host.docker.internal:8101 → ASR Service
host.docker.internal:8102 → vLLM Service
```

### 3. 构建和启动

```bash
# 手动构建（可选）
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 访问地址

**本地访问：**
```
https://localhost
https://127.0.0.1
```

**远程访问：**
```
https://10.161.176.132
```

**HTTP自动重定向到HTTPS：**
```
http://10.161.176.132 → https://10.161.176.132
```

---

## 🛠️ 管理命令

### 查看状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 所有服务
docker-compose logs -f

# Voice Bot服务
docker logs -f dualeye-voicebot

# Nginx服务
docker logs -f dualeye-nginx
```

### 重启服务

```bash
# 重启所有
docker-compose restart

# 重启单个服务
docker-compose restart voicebot
docker-compose restart nginx
```

### 停止服务

```bash
docker-compose down
```

### 完全清理

```bash
# 停止并删除容器、网络
docker-compose down

# 删除镜像
docker-compose down --rmi all

# 删除所有数据
docker-compose down -v
```

---

## 🔧 配置文件

### docker-compose.yml

主配置文件，定义两个服务：
- `voicebot` - Flask应用
- `nginx` - 反向代理

### nginx.conf

Nginx配置：
- HTTP → HTTPS 重定向
- WebSocket支持
- 长连接超时配置
- SSL/TLS优化

### Dockerfile

Voice Bot镜像构建：
- 基于 Python 3.11-slim
- 安装依赖
- 健康检查

---

## 🐛 故障排查

### 问题1: 容器无法启动

```bash
# 查看详细日志
docker-compose logs voicebot

# 检查端口占用
netstat -tuln | grep -E "443|8888"

# 确保旧进程已停止
pkill -f "python.*app.py"
```

### 问题2: 无法访问后端服务

**原因**: Docker容器无法访问宿主机的 localhost

**解决**: 使用 `host.docker.internal`

配置已自动处理：
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### 问题3: SSL证书警告

**正常现象**，自签名证书会有警告。

在浏览器点击：
- "高级" → "继续访问"

### 问题4: WebSocket连接失败

检查Nginx配置：
```bash
docker exec dualeye-nginx nginx -t
```

查看Nginx日志：
```bash
docker logs dualeye-nginx
```

---

## 📊 性能监控

### 资源使用

```bash
# CPU和内存
docker stats dualeye-voicebot

# 详细信息
docker inspect dualeye-voicebot
```

### 健康检查

```bash
# 检查健康状态
docker inspect --format='{{.State.Health.Status}}' dualeye-voicebot

# 查看健康检查日志
docker inspect --format='{{json .State.Health}}' dualeye-voicebot | jq
```

---

## 🔒 安全配置

### 生产环境SSL证书

替换自签名证书为正式证书：

```bash
# 1. 获取Let's Encrypt证书（需要域名）
certbot certonly --standalone -d your-domain.com

# 2. 更新docker-compose.yml
volumes:
  - /etc/letsencrypt/live/your-domain.com/fullchain.pem:/etc/nginx/cert.pem:ro
  - /etc/letsencrypt/live/your-domain.com/privkey.pem:/etc/nginx/key.pem:ro

# 3. 重启
docker-compose restart nginx
```

### 限制访问IP（可选）

编辑 `nginx.conf`：

```nginx
server {
    listen 443 ssl;
    
    # 只允许特定IP
    allow 10.161.176.0/24;
    allow 192.168.1.0/24;
    deny all;
    
    # ... 其他配置
}
```

---

## 📈 扩展配置

### 修改端口

编辑 `docker-compose.yml`：

```yaml
services:
  nginx:
    ports:
      - "8443:443"  # 使用8443端口
      - "8080:80"
```

### 添加环境变量

```yaml
services:
  voicebot:
    environment:
      - LOG_LEVEL=DEBUG
      - MAX_TOKENS=256
```

### 持久化日志

```yaml
services:
  voicebot:
    volumes:
      - ./logs:/app/logs
```

---

## ✅ 部署检查清单

部署前检查：

- [ ] Docker已安装并运行
- [ ] Docker Compose已安装
- [ ] ASR Service运行在8101端口
- [ ] vLLM Service运行在8102端口
- [ ] 端口443和80未被占用
- [ ] SSL证书已生成

部署后验证：

- [ ] 容器运行正常 (`docker-compose ps`)
- [ ] 日志无错误 (`docker-compose logs`)
- [ ] HTTPS访问成功
- [ ] 麦克风权限正常
- [ ] 语音识别工作
- [ ] LLM回复正常

---

## 🎯 访问测试

### 本地测试

```bash
# HTTPS
curl -k https://localhost

# 检查重定向
curl -I http://localhost
```

### 远程测试

从其他设备浏览器访问：
```
https://10.161.176.132
```

接受证书警告后即可使用。

---

## 📝 更新应用

```bash
# 1. 停止服务
docker-compose down

# 2. 修改代码

# 3. 重新构建
docker-compose build

# 4. 启动
docker-compose up -d
```

或使用脚本：
```bash
./deploy_docker.sh
```

---

## 🎉 完成

现在你有一个生产级的Docker部署方案！

**访问**: `https://10.161.176.132`

**管理**: `docker-compose logs -f`

**停止**: `docker-compose down`
