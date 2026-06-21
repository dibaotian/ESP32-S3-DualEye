// DualEye Voice Bot - Frontend Application

class VoiceBot {
    constructor() {
        // WebSocket connection
        this.socket = io();

        // Audio context and processing
        this.audioContext = null;
        this.mediaStreamSource = null;
        this.workletNode = null;
        this.audioStream = null;

        // Audio playback queue
        this.audioQueue = [];
        this.isPlaying = false;
        this.audioPlaybackRate = 24000;  // MeloTTS output rate

        // State
        this.isRecording = false;
        this.isConnected = false;
        this.isTTSPlaying = false;  // mute mic during TTS playback
        this.ttsResumeTimer = null;

        // DOM elements
        this.startBtn = document.getElementById('start-btn');
        this.resetBtn = document.getElementById('reset-btn');
        this.chatMessages = document.getElementById('chat-messages');
        this.statusText = document.querySelector('.status .text');
        this.statusDot = document.querySelector('.status .dot');

        this.init();
    }

    init() {
        // Setup event listeners
        this.startBtn.addEventListener('click', () => this.toggleRecording());
        this.resetBtn.addEventListener('click', () => this.resetConversation());

        // Setup SocketIO listeners
        this.setupSocketIO();
    }

    setupSocketIO() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.isConnected = true;
            this.updateStatus('已连接', 'connected');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.isConnected = false;
            this.updateStatus('已断开', 'disconnected');
        });

        this.socket.on('status', (data) => {
            console.log('Status:', data.message);
            this.addSystemMessage(data.message);
        });

        this.socket.on('user_message', (data) => {
            console.log('[SocketIO] User message received:', data.text);
            this.addUserMessage(data.text);
        });

        this.socket.on('llm_message', (data) => {
            console.log('[SocketIO] LLM message received:', data.text);
            this.addLLMMessage(data.text);
        });

        this.socket.on('status', (data) => {
            console.log('[SocketIO] Status:', data.message);
            this.addSystemMessage(data.message);
        });

        this.socket.on('play_audio_stream', (data) => {
            console.log('Received audio chunk:', data.chunk_index + '/' + data.total_chunks);
            this.queueAudioChunk(data.data, data.sample_rate);
        });

        this.socket.on('tts_start', () => {
            console.log('[TTS] Started - muting microphone');
            this.isTTSPlaying = true;
            if (this.ttsResumeTimer) clearTimeout(this.ttsResumeTimer);
            this.updateStatus('AI正在说话...', 'recording');
        });

        this.socket.on('tts_end', (data) => {
            const delay = (data.duration_ms || 1000) + 800;  // audio duration + 800ms tail buffer
            console.log(`[TTS] Ended - resuming mic in ${delay}ms`);
            if (this.ttsResumeTimer) clearTimeout(this.ttsResumeTimer);
            this.ttsResumeTimer = setTimeout(() => {
                this.isTTSPlaying = false;
                if (this.isRecording) this.updateStatus('正在录音...', 'recording');
                console.log('[TTS] Mic unmuted');
            }, delay);
        });
    }

    async toggleRecording() {
        if (this.isRecording) {
            await this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            // Request microphone access
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });

            // Create audio context
            this.audioContext = new AudioContext({ sampleRate: 16000 });
            console.log('[Audio] AudioContext state:', this.audioContext.state, 'sampleRate:', this.audioContext.sampleRate);

            // Resume context if suspended (browser autoplay policy)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('[Audio] AudioContext resumed, state:', this.audioContext.state);
            }

            this.mediaStreamSource = this.audioContext.createMediaStreamSource(this.audioStream);

            // Load and create audio worklet for processing
            await this.audioContext.audioWorklet.addModule('/static/js/audio-processor.js?v=4');
            console.log('[Audio] AudioWorklet module loaded');
            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor');

            // Handle audio data from worklet
            this.workletNode.port.onmessage = (event) => {
                const audioData = event.data;
                // Diagnostic messages from worklet
                if (audioData && audioData.debug) {
                    console.log('[Audio] Worklet process() call', audioData.call,
                                '- channels:', audioData.inputChannels, 'samples:', audioData.samples);
                    return;
                }
                // Mute mic while TTS is playing to prevent echo
                if (this.isTTSPlaying) return;
                this.socket.emit('audio', audioData);
            };

            // Connect audio graph
            this.mediaStreamSource.connect(this.workletNode);
            this.workletNode.connect(this.audioContext.destination);

            // Update UI
            this.isRecording = true;
            this.startBtn.classList.add('active');
            this.startBtn.querySelector('.text').textContent = '停止对话';
            this.startBtn.querySelector('.icon').textContent = '⏹️';
            this.updateStatus('正在录音...', 'recording');

            console.log('Recording started');

        } catch (error) {
            console.error('Failed to start recording:', error);
            alert('无法访问麦克风，请检查权限设置');
        }
    }

    async stopRecording() {
        if (this.workletNode) {
            this.workletNode.disconnect();
            this.workletNode = null;
        }

        if (this.mediaStreamSource) {
            this.mediaStreamSource.disconnect();
            this.mediaStreamSource = null;
        }

        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }

        if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
        }

        // Notify server
        this.socket.emit('stop');

        // Update UI
        this.isRecording = false;
        this.startBtn.classList.remove('active');
        this.startBtn.querySelector('.text').textContent = '开始对话';
        this.startBtn.querySelector('.icon').textContent = '🎤';
        this.updateStatus('已连接', 'connected');

        console.log('Recording stopped');
    }

    resetConversation() {
        // Clear UI
        this.chatMessages.innerHTML = '<div class="system-message">对话已重置</div>';

        // Notify server
        this.socket.emit('reset');

        console.log('Conversation reset');
    }

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.textContent = '👤 ' + text;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addLLMMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message llm-message';
        messageDiv.textContent = '🤖 ' + text;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addSystemMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'system-message';
        messageDiv.textContent = text;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    updateStatus(text, state) {
        this.statusText.textContent = text;
        this.statusDot.className = 'dot';
        if (state) {
            this.statusDot.classList.add(state);
        }
    }

    scrollToBottom() {
        this.chatMessages.parentElement.scrollTop = this.chatMessages.parentElement.scrollHeight;
    }

    queueAudioChunk(base64Data, sampleRate) {
        // Decode base64 to ArrayBuffer
        const binaryString = atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Convert bytes to Float32Array
        const float32Array = new Float32Array(bytes.buffer);

        // Add to queue
        this.audioQueue.push({
            data: float32Array,
            sampleRate: sampleRate || this.audioPlaybackRate
        });

        // Start playback if not already playing
        if (!this.isPlaying) {
            this.playNextChunk();
        }
    }

    async playNextChunk() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }

        this.isPlaying = true;

        const chunk = this.audioQueue.shift();

        // Create audio context for playback if needed
        if (!this.audioContext || this.audioContext.state === 'closed') {
            this.audioContext = new AudioContext({ sampleRate: chunk.sampleRate });
        }

        // Create audio buffer
        const audioBuffer = this.audioContext.createBuffer(
            1,  // mono
            chunk.data.length,
            chunk.sampleRate
        );

        // Copy data to buffer
        audioBuffer.getChannelData(0).set(chunk.data);

        // Create buffer source
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);

        // Play next chunk when this one ends
        source.onended = () => {
            this.playNextChunk();
        };

        source.start();
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const voiceBot = new VoiceBot();
    console.log('DualEye Voice Bot initialized');
});
