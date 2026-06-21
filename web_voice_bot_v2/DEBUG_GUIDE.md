# 调试指南 - 麦克风和消息显示

## 🐛 当前问题

1. 麦克风打开但没有正确收音
2. STT和LLM消息需要在对话框中显示

## 🔍 调试步骤

### 1. 检查浏览器控制台

按 `F12` 打开开发者工具，查看Console标签：

**应该看到的日志**:
```
Connected to server
[Audio] Sending chunk, size: 16384
[SocketIO] User message received: 你好
[SocketIO] LLM message received: 你好！有什么可以帮助你的吗？
```

**如果没有 "[Audio] Sending chunk"**:
- 麦克风没有正确工作
- AudioWorklet加载失败

**如果没有消息日志**:
- 后端没有发送消息事件
- SocketIO连接问题

### 2. 检查后端日志

```bash
docker logs dualeye-voicebot -f
```

**应该看到**:
```
Received audio chunk: 16384 bytes
Sending 16384 bytes to VAD queue
✓ STT: '你好'
✓ LLM output: '你好！...'
```

### 3. 测试麦克风

在浏览器控制台运行：

```javascript
// 测试麦克风访问
navigator.mediaDevices.getUserMedia({audio: true})
  .then(stream => {
    console.log('✓ Microphone OK');
    console.log('Sample rate:', stream.getAudioTracks()[0].getSettings().sampleRate);
    stream.getTracks().forEach(t => t.stop());
  })
  .catch(err => console.error('✗ Microphone error:', err));
```

### 4. 测试AudioWorklet

```javascript
// 检查AudioWorklet加载
const ctx = new AudioContext();
ctx.audioWorklet.addModule('/static/js/audio-processor.js')
  .then(() => console.log('✓ AudioWorklet loaded'))
  .catch(err => console.error('✗ AudioWorklet error:', err));
```

## 🛠️ 常见问题修复

### 问题1: 麦克风无声音

**原因**: AudioContext采样率不匹配

**解决**: 修改 `app.js`
```javascript
// 确保采样率设置正确
this.audioContext = new AudioContext({ 
    sampleRate: 16000  // 必须16000
});
```

### 问题2: AudioWorklet加载失败

**检查**: 
1. `/static/js/audio-processor.js` 是否存在
2. 浏览器是否支持AudioWorklet (Chrome 66+)

**解决**: 刷新页面或清除缓存

### 问题3: 消息不显示

**原因**: SocketIO事件没有正确监听

**检查**: `app.js` 中是否有：
```javascript
this.socket.on('user_message', (data) => {
    this.addUserMessage(data.text);
});

this.socket.on('llm_message', (data) => {
    this.addLLMMessage(data.text);
});
```

### 问题4: VAD没有启动

**原因**: VAD模型加载失败（当前Docker版本）

**临时方案**: 跳过VAD，直接处理音频
- 修改后端让音频直接进入STT

## 📊 完整测试流程

1. **打开页面** → 看到"已连接"状态
2. **点击"开始对话"** → 按钮变红，显示"停止对话"
3. **说话** → 浏览器控制台出现 [Audio] 日志
4. **等待** → 看到蓝色用户消息气泡
5. **等待** → 看到橙色AI回复气泡

## 🔧 快速修复脚本

创建测试文件 `test.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Mic Test</title>
</head>
<body>
    <h1>Microphone Test</h1>
    <button id="start">Start</button>
    <button id="stop">Stop</button>
    <div id="log"></div>

    <script>
        let audioContext, workletNode, stream;
        const log = msg => {
            document.getElementById('log').innerHTML += msg + '<br>';
            console.log(msg);
        };

        document.getElementById('start').onclick = async () => {
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    }
                });
                log('✓ Got microphone');

                audioContext = new AudioContext({ sampleRate: 16000 });
                log('✓ AudioContext created: ' + audioContext.sampleRate + 'Hz');

                const source = audioContext.createMediaStreamSource(stream);
                log('✓ Audio source created');

                await audioContext.audioWorklet.addModule('/static/js/audio-processor.js');
                log('✓ Worklet loaded');

                workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
                workletNode.port.onmessage = (e) => {
                    log('📦 Audio chunk: ' + e.data.byteLength + ' bytes');
                };

                source.connect(workletNode);
                workletNode.connect(audioContext.destination);
                log('✓ Pipeline connected - speak now!');

            } catch (err) {
                log('✗ Error: ' + err.message);
            }
        };

        document.getElementById('stop').onclick = () => {
            if (stream) stream.getTracks().forEach(t => t.stop());
            if (audioContext) audioContext.close();
            log('⏹ Stopped');
        };
    </script>
</body>
</html>
```

访问 `https://10.161.176.132/test.html` 测试麦克风。

## 🎯 最终检查清单

- [ ] HTTPS访问（不是HTTP）
- [ ] 浏览器允许麦克风权限
- [ ] 系统麦克风正常工作
- [ ] 浏览器控制台无错误
- [ ] Docker容器运行正常
- [ ] ASR/vLLM服务正常
- [ ] SocketIO连接成功
- [ ] 后端接收到音频数据

## 📝 获取完整日志

```bash
# 前端日志（浏览器控制台）
# 按F12 → Console标签 → 复制所有内容

# 后端日志
docker logs dualeye-voicebot --tail 100 > backend.log
cat backend.log

# Nginx日志
docker logs dualeye-nginx --tail 50

# 网络检查
# F12 → Network标签 → 查看WebSocket连接状态
```

---

如果问题仍未解决，提供：
1. 浏览器控制台截图
2. 后端日志
3. 使用的浏览器和版本
