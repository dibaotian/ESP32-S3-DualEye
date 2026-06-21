#!/bin/bash
# DualEye Voice Bot v2 - Start Script

set -e

echo "=================================="
echo "DualEye Voice Bot v2 - 启动脚本"
echo "=================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在，请先运行 ./install.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required services are running
echo "检查依赖服务..."

# Check ASR Service (port 8101)
if curl -s http://localhost:8101/health > /dev/null 2>&1; then
    echo "✓ ASR Service (端口 8101) 正在运行"
else
    echo "⚠️ 警告: ASR Service (端口 8101) 未运行"
    echo "   请先启动 ASR_Service"
fi

# Check vLLM Service (port 8102)
if curl -s http://localhost:8102/health > /dev/null 2>&1; then
    echo "✓ vLLM Service (端口 8102) 正在运行"
else
    echo "⚠️ 警告: vLLM Service (端口 8102) 未运行"
    echo "   请先启动 vllm_Qwen3.5-35B-A3B-W4A16_Service"
fi

echo ""
echo "启动 Voice Bot Server..."
echo ""

# Parse command line arguments
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8888}"
SSL_CERT="${SSL_CERT:-}"
SSL_KEY="${SSL_KEY:-}"

# Build command
CMD="python app.py --host $HOST --port $PORT"

if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ]; then
    CMD="$CMD --ssl-cert $SSL_CERT --ssl-key $SSL_KEY"
    echo "SSL 已启用"
    echo "访问地址: https://<your-ip>:$PORT"
else
    echo "HTTP 模式 (推荐使用 HTTPS)"
    echo "访问地址: http://<your-ip>:$PORT"
fi

echo ""
echo "服务器监听: $HOST:$PORT"
echo ""

# Run server
exec $CMD
