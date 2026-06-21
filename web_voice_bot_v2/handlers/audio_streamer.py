"""
Audio Streamer Handler
将 TTS 生成的音频流式发送到客户端
"""

import logging
import numpy as np
import base64
from threading import Event
from queue import Queue

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler

logger = logging.getLogger(__name__)


class AudioStreamerHandler(BaseHandler):
    """
    Streams audio data to clients via SocketIO
    将音频数据实时发送到前端播放
    """

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue = None,
        setup_args=(),
        setup_kwargs=None,
        chunk_size: int = 4096,
    ):
        """
        Initialize Audio Streamer

        Args:
            chunk_size: Size of audio chunks to stream
        """
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)

        self.chunk_size = chunk_size

    def setup(self):
        """Setup audio streamer"""
        logger.info("Audio Streamer initialized")

    def process(self, input_data):
        """
        Stream audio to client

        Args:
            input_data: Audio data (numpy array)

        Returns:
            None (sends directly via SocketIO)
        """
        try:
            if not isinstance(input_data, np.ndarray) or input_data.size == 0:
                logger.warning(f"Invalid audio data: {type(input_data)}")
                return None

            # Ensure float32
            if input_data.dtype != np.float32:
                input_data = input_data.astype(np.float32)

            # Notify frontend to mute mic during TTS playback
            if self.socketio:
                self.socketio.emit('tts_start', {})

            # Stream audio in chunks
            num_chunks = (len(input_data) + self.chunk_size - 1) // self.chunk_size

            for i in range(num_chunks):
                start_idx = i * self.chunk_size
                end_idx = min(start_idx + self.chunk_size, len(input_data))
                chunk = input_data[start_idx:end_idx]

                audio_bytes = chunk.tobytes()
                encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')

                if self.socketio:
                    self.socketio.emit('play_audio_stream', {
                        'data': encoded_audio,
                        'sample_rate': 24000,
                        'chunk_index': i,
                        'total_chunks': num_chunks,
                    })
                else:
                    logger.warning("SocketIO not set, cannot stream audio")

            # Estimate playback duration and notify frontend after audio ends
            duration_ms = int(len(input_data) / 24000 * 1000)
            if self.socketio:
                self.socketio.emit('tts_end', {'duration_ms': duration_ms})

            logger.info(f"✓ Streamed {num_chunks} audio chunks ({len(input_data)} samples, {duration_ms}ms)")

            return None

        except Exception as e:
            logger.error(f"Audio streaming error: {e}", exc_info=True)
            return None
