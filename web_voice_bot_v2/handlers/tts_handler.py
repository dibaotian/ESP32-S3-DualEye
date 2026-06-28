"""
TTS Handler - calls edge-tts HTTP server running on the host (port 8200).
POST /tts {"text": "...", "voice": "..."}  → WAV bytes
Note: edge-tts uses Microsoft Azure TTS API (no GPU required)
"""

import io
import wave
import logging
import httpx
import numpy as np
from threading import Event
from queue import Queue

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler

logger = logging.getLogger(__name__)


class TTSHandler(BaseHandler):

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
        api_url: str = "http://host.docker.internal:8200/tts",
        voice: str = "zh-CN-XiaoxiaoNeural",  # edge-tts voice
        timeout: float = 30.0,
    ):
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)
        self.api_url = api_url
        self.voice = voice
        self.timeout = timeout
        self.client = None
        self.sample_rate = 24000

    def setup(self):
        self.client = httpx.Client(timeout=self.timeout)
        try:
            health_url = self.api_url.replace("/tts", "/health")
            r = self.client.get(health_url, timeout=5.0)
            if r.status_code == 200:
                logger.info(f"✓ TTS service ready at {self.api_url}")
            else:
                logger.warning(f"TTS health: {r.status_code}")
        except Exception as e:
            logger.warning(f"TTS health check failed: {e}")

    def process(self, input_data):
        text = input_data
        if not text or not isinstance(text, str):
            return None

        logger.info(f"TTS: '{text[:60]}'")

        try:
            # edge-tts API
            response = self.client.post(
                self.api_url,
                json={"text": text, "voice": self.voice},
            )
            response.raise_for_status()
            audio = self._wav_to_float32(response.content)
            logger.info(f"✓ TTS {len(audio)} samples ({len(audio)/self.sample_rate:.2f}s)")
            return audio
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    def _wav_to_float32(self, wav_bytes: bytes) -> np.ndarray:
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            self.sample_rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            n_ch = wf.getnchannels()
            sw = wf.getsampwidth()

        if sw == 2:
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 4:
            pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            pcm = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        if n_ch > 1:
            pcm = pcm.reshape(-1, n_ch).mean(axis=1)
        return pcm

    def cleanup(self):
        if self.client:
            self.client.close()
