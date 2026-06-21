"""
STT (Speech-to-Text) Handler
使用 ASR_Service (vLLM Qwen-ASR) 进行语音识别
"""

import logging
import numpy as np
import base64
import io
import wave
import httpx
from threading import Event
from queue import Queue

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler

logger = logging.getLogger(__name__)


class STTHandler(BaseHandler):
    """
    Speech-to-Text using ASR_Service API
    将语音转换为文本
    """

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
        api_url: str = "http://localhost:8101/v1/chat/completions",
        model: str = "Qwen/Qwen3-ASR-Flash",
        sample_rate: int = 16000,
        timeout: float = 30.0,
    ):
        """
        Initialize STT Handler

        Args:
            api_url: ASR Service API endpoint
            model: ASR model name
            sample_rate: Audio sample rate
            timeout: Request timeout
        """
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)

        self.api_url = api_url
        self.model = model
        self.sample_rate = sample_rate
        self.timeout = timeout

        self.client = None

    def setup(self):
        """Setup HTTP client and test connection"""
        try:
            logger.info(f"Setting up STT handler with API: {self.api_url}")

            # Create async HTTP client
            self.client = httpx.Client(timeout=self.timeout)

            # Test connection
            health_url = self.api_url.replace('/v1/chat/completions', '/health')
            try:
                response = self.client.get(health_url, timeout=5.0)
                if response.status_code == 200:
                    logger.info("✓ ASR Service is healthy and ready")
                else:
                    logger.warning(f"⚠️ ASR Service health check returned {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Cannot connect to ASR Service: {e}")
                logger.error(f"Please ensure ASR Service is running at {self.api_url}")

        except Exception as e:
            logger.error(f"STT setup failed: {e}", exc_info=True)
            raise

    def process(self, input_data):
        """
        Convert speech to text using ASR Service

        Args:
            input_data: Audio data (numpy array of float32 samples)

        Returns:
            Recognized text string
        """
        try:
            # Convert numpy array to base64 WAV
            audio_base64 = self._audio_to_base64(input_data, self.sample_rate)

            # Call ASR API
            transcript = self._call_asr_api(audio_base64)

            if transcript:
                logger.info(f"✓ STT: '{transcript}'")

                # Emit to frontend via SocketIO
                if self.socketio:
                    self.socketio.emit('user_message', {'text': transcript})

            return transcript

        except Exception as e:
            logger.error(f"STT processing error: {e}", exc_info=True)
            return None

    def _audio_to_base64(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """
        Convert audio numpy array to base64-encoded WAV

        Args:
            audio_data: Audio samples (float32)
            sample_rate: Sample rate

        Returns:
            Base64 string of WAV file
        """
        try:
            # Ensure float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Normalize to [-1, 1]
            if len(audio_data) > 0:
                max_val = np.abs(audio_data).max()
                if max_val > 1.0:
                    audio_data = audio_data / max_val

            # Convert to 16-bit PCM
            audio_int16 = (audio_data * 32767).astype(np.int16)

            # Create WAV file in memory
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())

            # Encode to base64
            buffer.seek(0)
            audio_bytes = buffer.read()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            return audio_base64

        except Exception as e:
            logger.error(f"Failed to convert audio to base64: {e}")
            raise

    def _call_asr_api(self, audio_base64: str) -> str:
        """
        Call ASR Service API

        Args:
            audio_base64: Base64-encoded WAV audio

        Returns:
            Transcribed text
        """
        try:
            response = self.client.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "audio_url",
                                    "audio_url": {
                                        "url": f"data:audio/wav;base64,{audio_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 512,
                },
            )

            response.raise_for_status()
            result = response.json()

            # Extract transcript and strip ASR format prefix:
            # e.g. "language Chinese<asr_text>你好" → "你好"
            raw = result["choices"][0]["message"]["content"].strip()
            if "<asr_text>" in raw:
                transcript = raw.split("<asr_text>", 1)[1].strip()
            else:
                transcript = raw

            return transcript if transcript else None

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ASR API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Failed to call ASR API: {e}")
            raise

    def cleanup(self):
        """Close HTTP client"""
        if self.client:
            self.client.close()
