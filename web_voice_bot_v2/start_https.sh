#!/bin/bash
cd /home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2

# 停止旧进程
pkill -f "python.*app.py" 2>/dev/null
sleep 2

# 启动HTTPS服务器
nohup venv/bin/python app.py --port 8888 \
  --ssl-cert cert.pem --ssl-key key.pem \
  > https_server.log 2>&1 &

# 等待启动
sleep 3

echo "=========================================="
echo " DualEye Voice Bot - HTTPS Server Started"
echo "=========================================="
echo ""
echo "✅ Server running with SSL/TLS"
echo ""
echo "📍 访问地址:"
echo "   https://127.0.0.1:8888"
echo "   https://localhost:8888"
echo ""
echo "⚠️  浏览器步骤:"
echo "   1. 访问上述地址"
echo "   2. 接受证书警告（点击'高级' -> '继续访问'）"
echo "   3. 点击'开始对话'按钮"
echo "   4. 允许麦克风权限"
echo "   5. 开始说话！"
echo ""
echo "📝 查看日志: tail -f voice_bot.log"
echo "🛑 停止服务: pkill -f 'python.*app.py'"
echo ""
