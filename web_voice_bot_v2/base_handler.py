"""
Base Handler for Pipeline Processing
基于 talk_with_llm_web_version 的架构
"""

import logging
from threading import Event
from queue import Queue
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """
    Base class for all pipeline handlers (VAD, STT, LLM, TTS)
    """

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
    ):
        """
        Initialize base handler

        Args:
            stop_event: Event to signal stop
            queue_in: Input queue
            queue_out: Output queue
            setup_args: Additional setup arguments
            setup_kwargs: Additional setup keyword arguments
        """
        self.stop_event = stop_event
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.setup_args = setup_args
        self.setup_kwargs = setup_kwargs or {}

        self.socketio = None  # Optional SocketIO instance for status updates

    def set_socketio(self, socketio):
        """Set SocketIO instance for real-time status updates"""
        self.socketio = socketio

    @abstractmethod
    def setup(self):
        """Setup handler resources (load models, etc.)"""
        pass

    @abstractmethod
    def process(self, input_data):
        """
        Process input data and return output

        Args:
            input_data: Input data from queue_in

        Returns:
            Output data to be put in queue_out
        """
        pass

    def run(self):
        """Main loop - continuously process data from queue"""
        logger.info(f"{self.__class__.__name__} started")

        # Setup resources
        try:
            self.setup()
        except Exception as e:
            logger.error(f"Setup failed for {self.__class__.__name__}: {e}", exc_info=True)
            return

        # Main processing loop
        while not self.stop_event.is_set():
            try:
                # Get input data from queue
                input_data = self.queue_in.get()

                # Check for stop signal (use `is` to avoid numpy array comparison)
                if input_data is None or (isinstance(input_data, (bytes, str)) and input_data in (b'END', 'END')):
                    logger.info(f"{self.__class__.__name__} received END signal")
                    break

                # Process data
                output_data = self.process(input_data)

                # Put output in queue (if any)
                if output_data is not None and self.queue_out is not None:
                    self.queue_out.put(output_data)

            except Exception as e:
                logger.error(f"Error in {self.__class__.__name__}: {e}", exc_info=True)

        logger.info(f"{self.__class__.__name__} stopped")

    def cleanup(self):
        """Cleanup resources (optional override)"""
        pass
