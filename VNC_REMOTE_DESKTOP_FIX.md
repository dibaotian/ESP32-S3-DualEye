# 远程桌面（noVNC）修复文档

**问题**: 界面远程桌面打开后显示"已断开"或灰色屏幕  
**修复时间**: 2026-06-29  
**状态**: ✅ 已解决

---

## 问题原因

### 1. VNC 服务缺失
- 初始配置中没有 VNC 服务器容器
- `docker-compose.yml` 中缺少 noVNC 相关配置
- 前端代码连接到 `ws://hostname:6080/websockify` 但该服务不存在

### 2. WebSocket 路径错误
- 初始前端代码使用 `ws://hostname:6080`（缺少 `/websockify` 路径）
- 导致连接失败

### 3. 容器内无浏览器
- 第一次尝试使用 `theasp/novnc:latest` 镜像
- 该镜像只有窗口管理器（fluxbox），没有预装浏览器
- 用户看到灰色屏幕（空桌面）

---

## 解决方案

### 1. 添加 noVNC + Firefox 容器

**文件**: `docker-compose.yml`

```yaml
  # noVNC + Firefox浏览器 - 远程桌面
  novnc-browser:
    image: accetto/ubuntu-vnc-xfce-firefox-g3:latest
    container_name: dualeye-novnc
    environment:
      - VNC_PW=vncpassword
      - VNC_RESOLUTION=1280x720
    ports:
      - "6080:6901"  # noVNC web接口
    restart: unless-stopped
    shm_size: '2gb'  # Firefox需要更大的共享内存
    networks:
      - voicebot-network
```

**关键配置**:
- 镜像: `accetto/ubuntu-vnc-xfce-firefox-g3:latest`
  - 包含 XFCE 桌面环境
  - 预装 Firefox 浏览器
  - 内置 TigerVNC + noVNC
- 端口映射: `6080:6901`（容器内 6901 → 宿主机 6080）
- 共享内存: `2gb`（Firefox 需要）
- 分辨率: `1280x720`

### 2. 修复前端 WebSocket 路径

**文件**: `templates/index.html`

**修改前**:
```javascript
const url = `ws://${window.location.hostname}:6080`;
```

**修改后**:
```javascript
const url = `ws://${window.location.hostname}:6080/websockify`;
```

**说明**: 添加 `/websockify` 路径以匹配 noVNC 的 WebSocket 端点

### 3. 启动 Firefox

Firefox 在容器启动后会自动运行，无需手动启动。

容器启动时会自动执行：
- Xvnc (VNC 服务器)
- XFCE 桌面环境
- Firefox 浏览器
- noVNC WebSocket 代理

---

## 验证步骤

### 1. 检查容器状态

```bash
docker ps | grep novnc
```

期望输出：
```
CONTAINER ID   IMAGE                                      STATUS
7d922e47f9c6   accetto/ubuntu-vnc-xfce-firefox-g3:latest  Up X minutes
```

### 2. 检查端口监听

```bash
netstat -tuln | grep 6080
```

期望输出：
```
tcp        0      0 0.0.0.0:6080            0.0.0.0:*               LISTEN
```

### 3. 检查 Firefox 进程

```bash
docker exec dualeye-novnc ps aux | grep firefox
```

期望看到多个 firefox 进程在运行。

### 4. 测试 HTTP 访问

```bash
curl -I http://localhost:6080/
```

期望返回：
```
HTTP/1.1 200 OK
Server: WebSockify Python/3.12.3
```

### 5. 浏览器测试

打开 `http://localhost:8888`，点击"远程桌面"按钮：
- ✅ 应该看到连接成功
- ✅ 应该看到 XFCE 桌面环境
- ✅ 应该看到 Firefox 浏览器窗口

---

## 架构说明

```
用户浏览器 (http://localhost:8888)
    ↓
Web Voice Bot (端口 8888)
    ↓ 点击"远程桌面"按钮
    ↓
前端 JavaScript (noVNC client)
    ↓ WebSocket
    ↓
ws://localhost:6080/websockify
    ↓
noVNC WebSocket Proxy (容器端口 6901)
    ↓ VNC 协议
    ↓
TigerVNC Server (端口 5901)
    ↓
Xvnc (虚拟 X 服务器 :1)
    ↓
XFCE 桌面环境
    ↓
Firefox 浏览器
```

---

## 相关文件

### 修改的文件
1. `docker-compose.yml` - 添加 novnc-browser 服务
2. `templates/index.html` - 修复 WebSocket 连接路径

### 容器内部结构

**容器**: `dualeye-novnc`

**关键进程**:
```
xinit       - X 初始化
Xvnc :1     - VNC 服务器（端口 5901）
startxfce4  - XFCE 桌面管理器
firefox     - Firefox 浏览器
websockify  - WebSocket → VNC 代理（端口 6901）
```

**配置目录**:
```
/home/headless/.config/tigervnc/  - VNC 配置
/home/headless/.mozilla/          - Firefox 配置
```

---

## 常见问题

### Q1: 连接显示"已断开"

**检查**:
```bash
# 1. 容器是否运行
docker ps | grep novnc

# 2. 端口是否正确
docker port dualeye-novnc

# 3. WebSocket 路径
# 应该是: ws://hostname:6080/websockify
```

**解决**:
```bash
# 重启容器
docker restart dualeye-novnc
```

### Q2: 看到灰色屏幕（空桌面）

**原因**: Firefox 未启动或桌面环境未就绪

**检查**:
```bash
docker exec dualeye-novnc ps aux | grep firefox
docker exec dualeye-novnc ps aux | grep xfce
```

**解决**:
```bash
# 手动启动 Firefox（通常不需要，会自动启动）
docker exec -d dualeye-novnc firefox
```

### Q3: 连接成功但很卡

**原因**: 
- 分辨率太高
- 网络延迟
- 容器资源不足

**解决**:
```yaml
# 降低分辨率（docker-compose.yml）
environment:
  - VNC_RESOLUTION=1024x768  # 改为更低分辨率
```

或者在前端代码中调整：
```javascript
rfb = new RFB(vncScreen, url, {
    credentials: { password: '' },
    scaleViewport: true,     // 缩放到适应
    resizeSession: false,
    qualityLevel: 6          // 降低质量（0-9，9最高）
});
```

### Q4: 需要密码

默认配置不需要密码（VNC_PW 仅用于直接 VNC 连接）。

如果需要设置密码：
```yaml
environment:
  - VNC_PW=your_password
```

然后在前端代码中提供：
```javascript
rfb = new RFB(vncScreen, url, {
    credentials: { password: 'your_password' },
    ...
});
```

---

## 镜像选择说明

### 尝试过的镜像

#### 1. `theasp/novnc:latest` ❌
- **优点**: 轻量（~250MB）
- **缺点**: 
  - 只有 fluxbox 窗口管理器
  - 没有预装浏览器
  - 用户看到灰色屏幕
- **结论**: 不适合需要浏览器的场景

#### 2. `accetto/ubuntu-vnc-xfce-firefox-g3:latest` ✅ (最终选择)
- **优点**:
  - 包含 XFCE 桌面环境（完整）
  - 预装 Firefox 浏览器
  - 自动启动所有服务
  - 稳定可靠
- **缺点**: 
  - 镜像较大（~1.5GB）
- **结论**: 适合需要完整桌面环境的场景

### 其他可选镜像

```yaml
# Chrome 浏览器版本
accetto/ubuntu-vnc-xfce-chromium-g3:latest

# 更轻量的版本（无桌面环境，只有浏览器）
linuxserver/firefox:latest
linuxserver/chromium:latest
```

---

## 性能优化建议

### 1. 降低分辨率
```yaml
environment:
  - VNC_RESOLUTION=1024x768  # 从 1280x720 降低
```

### 2. 调整质量设置
```javascript
// templates/index.html
rfb = new RFB(vncScreen, url, {
    credentials: { password: '' },
    scaleViewport: true,
    resizeSession: false,
    qualityLevel: 6,           // 质量 0-9，默认 6
    compressionLevel: 2        // 压缩 0-9，默认 2
});
```

### 3. 限制 Firefox 资源
```bash
# 进入容器
docker exec -it dualeye-novnc bash

# 编辑 Firefox 配置
vi /home/headless/.mozilla/firefox/*.default-release/prefs.js

# 添加：
user_pref("browser.tabs.remote.autostart", false);  # 禁用多进程
user_pref("gfx.webrender.enabled", false);          # 禁用硬件加速
```

---

## 启动和重启

### 启动服务
```bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2
docker compose up -d novnc-browser
```

### 重启服务
```bash
docker restart dualeye-novnc
```

### 停止服务
```bash
docker stop dualeye-novnc
```

### 查看日志
```bash
docker logs dualeye-novnc --tail 50
```

---

## 安全建议

### 1. 设置 VNC 密码（生产环境）
```yaml
environment:
  - VNC_PW=StrongPassword123!
```

### 2. 限制访问（仅本地）
```yaml
ports:
  - "127.0.0.1:6080:6901"  # 只允许本地访问
```

### 3. 使用 HTTPS
通过 Nginx 反向代理：
```nginx
location /vnc/ {
    proxy_pass http://localhost:6080/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## 总结

### 修复步骤回顾

1. ✅ 添加 `novnc-browser` 服务到 `docker-compose.yml`
2. ✅ 使用 `accetto/ubuntu-vnc-xfce-firefox-g3` 镜像（包含 Firefox）
3. ✅ 修复前端 WebSocket 路径（添加 `/websockify`）
4. ✅ 配置正确的端口映射（`6080:6901`）
5. ✅ 验证 Firefox 自动启动

### 最终配置

**Docker Compose**:
- 服务名: `novnc-browser`
- 镜像: `accetto/ubuntu-vnc-xfce-firefox-g3:latest`
- 端口: `6080:6901`
- 分辨率: `1280x720`

**前端连接**:
- URL: `ws://hostname:6080/websockify`
- 无需密码
- 自动缩放适配

### 用户体验

- ✅ 点击"远程桌面"按钮
- ✅ 3-5 秒内连接成功
- ✅ 看到 XFCE 桌面 + Firefox 浏览器
- ✅ 可以正常使用浏览器

---

**修复完成时间**: 2026-06-29 07:42  
**测试状态**: ✅ 通过  
**用户反馈**: 连接成功，可以看到桌面和浏览器
