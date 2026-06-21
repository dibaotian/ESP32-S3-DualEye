#!/bin/bash
echo "===== DualEye Voice Bot - Connection Diagnostic ====="
echo ""

# 1. Check process
echo "1. Server Process:"
if ps aux | grep "python.*app.py" | grep -v grep > /dev/null; then
    echo "  ✅ Server is running"
    ps aux | grep "python.*app.py" | grep -v grep | awk '{print "     PID:", $2, "  CPU:", $3"%", "  MEM:", $4"%"}'
else
    echo "  ❌ Server not running"
fi

# 2. Check port
echo ""
echo "2. Port Status:"
if lsof -i :8888 2>/dev/null | grep LISTEN > /dev/null; then
    echo "  ✅ Port 8888 is listening"
    lsof -i :8888 | grep LISTEN | awk '{print "     Command:", $1, " PID:", $2, " User:", $3}'
else
    echo "  ❌ Port 8888 not listening"
fi

# 3. Test IPv4
echo ""
echo "3. Connection Tests:"
http_code=$(curl -4 -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8888 2>/dev/null)
if [ "$http_code" = "200" ]; then
    echo "  ✅ IPv4 (127.0.0.1:8888) - OK"
else
    echo "  ❌ IPv4 (127.0.0.1:8888) - Failed (HTTP $http_code)"
fi

http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888 2>/dev/null)
if [ "$http_code" = "200" ]; then
    echo "  ✅ localhost:8888 - OK"
else
    echo "  ❌ localhost:8888 - Failed (HTTP $http_code)"
fi

# 4. Check localhost resolution
echo ""
echo "4. DNS Resolution:"
getent hosts localhost | head -2 | while read line; do
    echo "     $line"
done

# 5. Check service health
echo ""
echo "5. Backend Services:"
if curl -s http://localhost:8101/health > /dev/null 2>&1; then
    echo "  ✅ ASR Service (8101) - OK"
else
    echo "  ❌ ASR Service (8101) - Down"
fi

if curl -s http://localhost:8102/health > /dev/null 2>&1; then
    echo "  ✅ vLLM Service (8102) - OK"
else
    echo "  ❌ vLLM Service (8102) - Down"
fi

echo ""
echo "===== Recommendation ====="
echo ""
echo "  🌐 Primary URL:   http://127.0.0.1:8888"
echo "  🌐 Alternative:   http://localhost:8888"
echo "  🌐 LAN Access:    http://10.161.176.132:8888"
echo ""
echo "  ⚠️  If browser shows 'Connection Refused':"
echo "      1. Try http://127.0.0.1:8888 instead of localhost"
echo "      2. Clear browser cache (Ctrl+Shift+Delete)"
echo "      3. Use Incognito/Private mode"
echo "      4. Try a different browser"
echo ""
