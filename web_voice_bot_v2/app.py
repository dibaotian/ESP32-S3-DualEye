"""
Low-Latency Voice Bot Server
基于 talk_with_llm_web_version 架构
使用 ASR_Service + vLLM Qwen3.5 + MeloTTS
"""

import os
import sys
import time
import shutil
import logging
import threading
import subprocess
from threading import Event
from queue import Queue

import numpy as np
from flask import Flask, render_template
from flask_socketio import SocketIO

# Add handlers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'handlers'))

from vad_handler import VADHandler
from stt_handler import STTHandler
from llm_handler import LLMHandler
from codex_handler import CodexHandler
from tts_handler import TTSHandler
from audio_streamer import AudioStreamerHandler

# Agent brain选择: "codex" 用 Codex(本地 vLLM, 带跨轮记忆) | "vllm" 用旧的直连 LLMHandler
AGENT_BACKEND = os.environ.get("AGENT_BACKEND", "codex")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Manages multiple threads for pipeline handlers
    """

    def __init__(self, handlers):
        self.handlers = handlers
        self.threads = []

    def start(self):
        """Start all handler threads"""
        for handler in self.handlers:
            thread = threading.Thread(target=handler.run, daemon=True)
            self.threads.append(thread)
            thread.start()
        logger.info(f"Started {len(self.threads)} handler threads")

    def stop(self):
        """Stop all handler threads"""
        for handler in self.handlers:
            handler.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5.0)
        logger.info("All handler threads stopped")


# Create Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'dualeye-voice-bot-secret'

# Create SocketIO instance
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
stop_event = Event()
should_listen = Event()
should_listen.set()  # Initially listening

# Pipeline queues
recv_audio_queue = Queue()
vad_output_queue = Queue()
stt_output_queue = Queue()
llm_output_queue = Queue()
tts_output_queue = Queue()

# Pipeline manager
pipeline_manager = None

# Codex 归一化代理进程 + 当前活跃 client(单用户用默认)
proxy_proc = None
codex_handler_ref = None
active_client_id = "default"


def _node_bin_dir():
    """找到 node/codex 所在目录 (codex CLI 子进程需要 node 在 PATH)。"""
    codex_path = shutil.which("codex")
    if codex_path:
        return os.path.dirname(os.path.realpath(codex_path))
    # 兜底:常见 nvm 路径
    import glob
    for p in sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")), reverse=True):
        if os.path.exists(os.path.join(p, "codex")):
            return p
    return None


def start_codex_proxy():
    """启动 Codex→vLLM 归一化代理 (若未运行)。"""
    global proxy_proc
    import urllib.request
    port = int(os.environ.get("PROXY_PORT", "8210"))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        logger.info("Codex proxy already running on :%d", port)
        return
    except Exception:
        pass

    proxy_script = os.path.join(os.path.dirname(__file__), "agent", "codex_vllm_proxy.py")
    vllm_base = os.environ.get("VLLM_SERVICE_URL", "http://localhost:8102") + "/v1"
    env = os.environ.copy()
    env["PROXY_PORT"] = str(port)
    env["VLLM_BASE_URL"] = vllm_base
    proxy_proc = subprocess.Popen([sys.executable, proxy_script], env=env)
    logger.info("Started Codex proxy (pid=%s) :%d → %s", proxy_proc.pid, port, vllm_base)

    # 等待就绪
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            logger.info("✓ Codex proxy is ready")
            return
        except Exception:
            time.sleep(0.5)
    logger.warning("⚠️ Codex proxy did not become ready in time")


class SimpleVAD:
    """
    Lightweight energy-based Voice Activity Detector.

    Replaces Silero VAD (which fails to download in Docker due to GitHub rate
    limits). Detects speech via RMS energy and segments complete utterances
    using a trailing-silence timeout, so the STT handler receives one numpy
    float32 array per spoken phrase instead of raw byte fragments.
    """

    def __init__(self, sample_rate=16000, energy_threshold=0.015,
                 min_speech_ms=300, silence_end_ms=700, max_speech_ms=15000):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.min_speech_samples = int(sample_rate * min_speech_ms / 1000)
        self.silence_end_samples = int(sample_rate * silence_end_ms / 1000)
        self.max_speech_samples = int(sample_rate * max_speech_ms / 1000)
        self.reset()

    def reset(self):
        self.speech_buffer = []
        self.speech_len = 0
        self.silence_samples = 0
        self.in_speech = False

    def process(self, samples: np.ndarray):
        """Feed a chunk of float32 samples. Returns a complete utterance
        (np.float32 array) when speech ends, otherwise None."""
        if len(samples) == 0:
            return None

        rms = float(np.sqrt(np.mean(samples ** 2)))
        is_speech = rms > self.energy_threshold

        if is_speech:
            if not self.in_speech:
                self.in_speech = True
                logger.debug(f"VAD: speech start (rms={rms:.4f})")
            self.speech_buffer.append(samples)
            self.speech_len += len(samples)
            self.silence_samples = 0
        elif self.in_speech:
            # Keep buffering trailing silence; it's part of the utterance
            self.speech_buffer.append(samples)
            self.speech_len += len(samples)
            self.silence_samples += len(samples)
            if self.silence_samples >= self.silence_end_samples:
                return self._flush()

        if self.speech_len >= self.max_speech_samples:
            logger.debug("VAD: max length reached, force flush")
            return self._flush()

        return None

    def _flush(self):
        if self.speech_len < self.min_speech_samples:
            self.reset()
            return None
        utterance = np.concatenate(self.speech_buffer)
        self.reset()
        return utterance


# Per-server VAD state (single client at a time)
# 增加 min_speech_ms 到 2000ms (2秒)，过滤掉 TTS 回音和环境噪音导致的误识别
vad_state = SimpleVAD(min_speech_ms=2000)


@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    """Client connected"""
    logger.info("Client connected")
    socketio.emit('status', {'message': 'Connected to voice bot server'})


@socketio.on('register')
def handle_register(data):
    """
    前端注册稳定的 client_id(localStorage 里的固定 UUID)。
    单用户:记录为活跃 client,刷新不丢记忆。
    多用户(将来):用它把每个连接映射到独立 thread。
    """
    global active_client_id
    if isinstance(data, dict) and data.get('clientId'):
        active_client_id = str(data['clientId'])
        logger.info("Registered client_id=%s", active_client_id)
        socketio.emit('status', {'message': 'Session registered'})


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    logger.info("Client disconnected")


@socketio.on('audio')
def handle_audio(data):
    """
    Receive audio data from client.
    Client sends PCM float32 audio at 16kHz. We run energy-based VAD here and
    push one complete utterance (numpy float32 array) to the STT queue.
    """
    if not isinstance(data, (bytes, bytearray)):
        logger.warning(f"Ignoring non-bytes audio: {type(data)}")
        return

    samples = np.frombuffer(data, dtype=np.float32)
    utterance = vad_state.process(samples)

    if utterance is not None:
        duration = len(utterance) / vad_state.sample_rate
        logger.info(f"🎤 Utterance detected: {len(utterance)} samples ({duration:.2f}s) → STT")
        recv_audio_queue.put(utterance)


@socketio.on('stop')
def handle_stop():
    """Stop recording: flush any in-progress utterance, then reset VAD."""
    logger.info("Stop signal received")
    # Flush remaining buffered speech as a final utterance
    if vad_state.in_speech and vad_state.speech_len >= vad_state.min_speech_samples:
        utterance = np.concatenate(vad_state.speech_buffer)
        recv_audio_queue.put(utterance)
        logger.info(f"🎤 Final utterance on stop: {len(utterance)} samples")
    vad_state.reset()


@socketio.on('reset')
def handle_reset():
    """Reset conversation"""
    logger.info("Reset conversation")
    vad_state.reset()
    # Clear queues
    while not recv_audio_queue.empty():
        recv_audio_queue.get()
    while not vad_output_queue.empty():
        vad_output_queue.get()
    while not stt_output_queue.empty():
        stt_output_queue.get()
    while not llm_output_queue.empty():
        llm_output_queue.get()
    while not tts_output_queue.empty():
        tts_output_queue.get()

    # 清掉 Codex 会话(忘记历史,开新 thread)
    if codex_handler_ref is not None:
        try:
            codex_handler_ref.reset_session(active_client_id)
        except Exception as e:
            logger.warning("reset_session failed: %s", e)

    socketio.emit('status', {'message': 'Conversation reset'})


def create_pipeline():
    """Create processing pipeline with all handlers"""
    global pipeline_manager

    logger.info("=" * 70)
    logger.info("Initializing Voice Bot Pipeline")
    logger.info("=" * 70)

    # VAD is optional - skip if model loading fails in Docker
    vad_enabled = False  # Set to True when VAD model is available

    if vad_enabled:
        vad = VADHandler(
            stop_event=stop_event,
            queue_in=recv_audio_queue,
            queue_out=vad_output_queue,
            setup_args=(should_listen,),
            sample_rate=16000,
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=500,
        )
        stt_input_queue = vad_output_queue
    else:
        logger.warning("⚠️  VAD disabled - audio goes directly to STT")
        vad = None
        stt_input_queue = recv_audio_queue  # Direct audio to STT

    stt = STTHandler(
        stop_event=stop_event,
        queue_in=stt_input_queue,
        queue_out=stt_output_queue,
        api_url=os.environ.get("ASR_SERVICE_URL", "http://host.docker.internal:8101") + "/v1/chat/completions",
        model="Qwen/Qwen3-ASR-0.6B",  # 使用实际模型名称
        sample_rate=16000,
        timeout=30.0,
    )
    stt.set_socketio(socketio)

    global codex_handler_ref
    if AGENT_BACKEND == "codex":
        # 先把归一化代理拉起来,Codex 才能打到本地 vLLM
        start_codex_proxy()
        llm = CodexHandler(
            stop_event=stop_event,
            queue_in=stt_output_queue,
            queue_out=llm_output_queue,
            node_bin_dir=_node_bin_dir(),
            timeout=float(os.environ.get("CODEX_TIMEOUT", "150")),
        )
        codex_handler_ref = llm
        logger.info("🧠 Agent backend: Codex (local vLLM, 跨轮记忆)")
    else:
        llm = LLMHandler(
            stop_event=stop_event,
            queue_in=stt_output_queue,
            queue_out=llm_output_queue,
            api_url=os.environ.get("VLLM_SERVICE_URL", "http://host.docker.internal:8102") + "/v1/chat/completions",
            model="/home/xilinx/.cache/huggingface/hub/models--local--Qwen3.5-35B-A3B-W4A16-llmcompressor",
            temperature=0.7,
            max_tokens=1024,
            timeout=60.0,
        )
        logger.info("🧠 Agent backend: vLLM (直连, 无长期记忆)")
    llm.set_socketio(socketio)

    # TTS via edge-tts service (Microsoft Azure TTS, no GPU required)
    tts_enabled = True

    if tts_enabled:
        tts = TTSHandler(
            stop_event=stop_event,
            queue_in=llm_output_queue,
            queue_out=tts_output_queue,
            api_url=os.environ.get("TTS_SERVICE_URL", "http://host.docker.internal:8200") + "/tts",
            voice="zh-CN-XiaoxiaoNeural",  # edge-tts voice: zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural, etc.
            timeout=30.0,
        )
        tts.set_socketio(socketio)

        audio_streamer = AudioStreamerHandler(
            stop_event=stop_event,
            queue_in=tts_output_queue,
            queue_out=None,
            chunk_size=4096,
        )
        audio_streamer.set_socketio(socketio)

        handlers = [h for h in [vad, stt, llm, tts, audio_streamer] if h]
    else:
        logger.warning("⚠️  TTS disabled - text-only mode")
        handlers = [h for h in [vad, stt, llm] if h]

    # Create thread manager
    pipeline_manager = ThreadManager(handlers)

    # Start pipeline
    pipeline_manager.start()

    logger.info("=" * 70)
    logger.info("Pipeline initialized successfully")
    logger.info("=" * 70)

    return pipeline_manager


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Low-Latency Voice Bot Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8888, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--ssl-cert', help='Path to SSL certificate')
    parser.add_argument('--ssl-key', help='Path to SSL key')

    args = parser.parse_args()

    # Create pipeline
    pm = create_pipeline()

    # Prepare SSL context if provided
    ssl_context = None
    if args.ssl_cert and args.ssl_key:
        ssl_context = (args.ssl_cert, args.ssl_key)
        logger.info(f"SSL enabled with cert: {args.ssl_cert}")

    try:
        logger.info(f"Starting server on {args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop")

        # Run server
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            ssl_context=ssl_context,
            allow_unsafe_werkzeug=True,  # For development/testing
        )

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_event.set()
        if pm:
            pm.stop()
        if proxy_proc is not None:
            logger.info("Stopping Codex proxy (pid=%s)", proxy_proc.pid)
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except Exception:
                proxy_proc.kill()

    logger.info("Server stopped")


if __name__ == '__main__':
    main()
