#!/bin/bash
# DualEye Voice Bot - Docker部署脚本

set -e

cd "$(dirname "$0")"

echo "========================================"
echo "  DualEye Voice Bot - Docker部署"
echo "========================================"
echo ""

# 1. 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose未安装"
    exit 1
fi

echo "✅ Docker已安装"
echo ""

# 2. 检查SSL证书
if [ ! -f cert.pem ] || [ ! -f key.pem ]; then
    echo "📝 生成SSL证书..."
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout key.pem -out cert.pem -days 365 \
        -subj "/CN=voicebot" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.161.176.132"
    echo "✅ SSL证书已生成"
else
    echo "✅ SSL证书已存在"
fi
echo ""

# 3. 检查后端服务
echo "📡 检查后端服务..."
if curl -s http://localhost:8101/health > /dev/null 2>&1; then
    echo "  ✅ ASR Service (8101) - 运行中"
else
    echo "  ❌ ASR Service (8101) - 未运行"
    echo "     请先启动 ASR_Service"
fi

if curl -s http://localhost:8102/health > /dev/null 2>&1; then
    echo "  ✅ vLLM Service (8102) - 运行中"
else
    echo "  ❌ vLLM Service (8102) - 未运行"
    echo "     请先启动 vLLM Service"
fi
echo ""

# 4. 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true
pkill -f "python.*app.py" 2>/dev/null || true
echo ""

# 5. 构建镜像
echo "🔨 构建Docker镜像..."
docker-compose build || docker compose build
echo ""

# 6. 启动服务
echo "🚀 启动服务..."
docker-compose up -d || docker compose up -d
echo ""

# 7. 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 8. 检查状态
echo ""
echo "📊 服务状态:"
docker-compose ps || docker compose ps
echo ""

# 9. 测试访问
echo "🧪 测试访问..."
if curl -k -s https://localhost > /dev/null 2>&1; then
    echo "  ✅ HTTPS访问正常"
else
    echo "  ⚠️  HTTPS访问失败，查看日志"
fi
echo ""

# 10. 显示访问信息
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "📍 访问地址:"
echo "   https://localhost"
echo "   https://127.0.0.1"
echo "   https://10.161.176.132"
echo ""
echo "🎯 从其他设备访问:"
echo "   https://10.161.176.132"
echo ""
echo "📝 查看日志:"
echo "   docker-compose logs -f"
echo "   或"
echo "   docker logs -f dualeye-voicebot"
echo ""
echo "🛑 停止服务:"
echo "   docker-compose down"
echo ""
echo "🔄 重启服务:"
echo "   docker-compose restart"
echo ""
