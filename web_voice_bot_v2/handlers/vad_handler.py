"""
VAD (Voice Activity Detection) Handler
使用 Silero VAD 进行语音活动检测
"""

import logging
import numpy as np
import torch
from threading import Event
from queue import Queue

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler

logger = logging.getLogger(__name__)


class VADHandler(BaseHandler):
    """
    Voice Activity Detection using Silero VAD
    检测语音活动并将有效语音片段传递给 STT
    """

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
    ):
        """
        Initialize VAD Handler

        Args:
            sample_rate: Audio sample rate (16000 Hz)
            threshold: VAD threshold (0.0 - 1.0)
            min_speech_duration_ms: Minimum speech duration in ms
            min_silence_duration_ms: Minimum silence duration to end speech
        """
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)

        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms

        self.model = None
        self.current_speech = []
        self.is_speaking = False
        self.silence_duration = 0

        # Extract should_listen event if provided
        self.should_listen = None
        if setup_args:
            self.should_listen = setup_args[0] if isinstance(setup_args[0], Event) else None

    def setup(self):
        """Load Silero VAD model"""
        try:
            logger.info("Loading Silero VAD model...")

            # Load Silero VAD model from torchhub
            # Set trust_repo for Docker/non-interactive environments
            import os
            os.environ['TORCH_HOME'] = '/tmp/torch'

            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,
                trust_repo=True,  # Auto-trust for non-interactive environments
            )

            logger.info("✓ Silero VAD model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load VAD model: {e}", exc_info=True)
            raise

    def process(self, input_data):
        """
        Process audio chunk for voice activity detection

        Args:
            input_data: Raw PCM audio bytes (float32)

        Returns:
            Complete speech segment when detected, None otherwise
        """
        try:
            # Check if we should listen (if TTS is playing, skip)
            if self.should_listen and not self.should_listen.is_set():
                return None

            # Convert bytes to numpy array
            audio_chunk = np.frombuffer(input_data, dtype=np.float32)

            # Ensure we have enough samples (at least 512 samples for VAD)
            if len(audio_chunk) < 512:
                return None

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_chunk)

            # Get VAD probability
            speech_prob = self.model(audio_tensor, self.sample_rate).item()

            # logger.debug(f"VAD prob: {speech_prob:.3f}")

            # Voice activity detection logic
            if speech_prob > self.threshold:
                # Speech detected
                self.current_speech.append(audio_chunk)
                self.is_speaking = True
                self.silence_duration = 0

            elif self.is_speaking:
                # Silence during speech
                self.current_speech.append(audio_chunk)
                self.silence_duration += len(audio_chunk) / self.sample_rate * 1000  # ms

                # Check if silence duration exceeds threshold
                if self.silence_duration >= self.min_silence_duration_ms:
                    # End of speech detected
                    speech_segment = np.concatenate(self.current_speech)

                    # Check minimum speech duration
                    speech_duration_ms = len(speech_segment) / self.sample_rate * 1000
                    if speech_duration_ms >= self.min_speech_duration_ms:
                        logger.info(f"✓ Speech detected: {speech_duration_ms:.0f} ms, {len(speech_segment)} samples")

                        # Reset state
                        self.current_speech = []
                        self.is_speaking = False
                        self.silence_duration = 0

                        # Return speech segment for STT
                        return speech_segment
                    else:
                        # Too short, reset
                        logger.debug(f"Speech too short: {speech_duration_ms:.0f} ms")
                        self.current_speech = []
                        self.is_speaking = False
                        self.silence_duration = 0

            return None

        except Exception as e:
            logger.error(f"VAD processing error: {e}", exc_info=True)
            return None
