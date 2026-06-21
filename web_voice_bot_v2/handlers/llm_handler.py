"""
LLM Handler
使用 vLLM Qwen3.5-35B 进行对话生成
"""

import re
import logging
import httpx
from threading import Event
from queue import Queue
from typing import List, Dict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler

logger = logging.getLogger(__name__)


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting so TTS reads clean spoken text."""
    # Bold/italic: **text** / *text* / __text__ / _text_
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Headers: # ## ###
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Inline code: `code`
    text = re.sub(r'`([^`]*)`', r'\1', text)
    # Code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Links: [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Blockquotes: > text
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Cleanup extra whitespace/blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_answer(text: str) -> str:
    """Extract the actual answer, stripping any chain-of-thought / thinking section."""

    # 1. Explicit answer-section markers (most reliable)
    for marker in ['**Final Response:**', 'Final Response:',
                   '**Response:**', 'Response:',
                   '**回复:**', '**回答:**', '**答:**']:
        if marker in text:
            answer = text.split(marker, 1)[1].strip()
            # Strip trailing markdown bold headers that sometimes follow
            answer = re.sub(r'^\*\*[^*]+\*\*\s*:?\s*', '', answer).strip()
            if answer:
                return answer

    # 2. If the text contains English-heavy thinking patterns, extract Chinese tail
    thinking_indicators = [
        'Thinking Process', 'Analyze the Request', '* **Role:**',
        '* **Task:**', '* **Input:**', '* **Style:**', 'Selecting the Best',
        'Determine the Response', 'Drafting the Response',
    ]
    has_thinking = any(ind in text for ind in thinking_indicators)

    if has_thinking:
        # Collect all paragraphs that are predominantly Chinese
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        chinese_paras = []
        for para in paragraphs:
            total = len(para)
            chinese = sum(1 for c in para if '一' <= c <= '鿿')
            if total > 0 and chinese / total > 0.3 and chinese >= 2:
                chinese_paras.append(para)

        if chinese_paras:
            # Return the last (most likely the actual response)
            answer = chinese_paras[-1]
            answer = re.sub(r'^\*\*[^*]+\*\*\s*:?\s*', '', answer).strip()
            return answer

        # No Chinese found - model responded in English; return last paragraph
        return paragraphs[-1] if paragraphs else text

    return text


class LLMHandler(BaseHandler):
    """
    Large Language Model Handler using vLLM API
    生成对话回复
    """

    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
        api_url: str = "http://localhost:8102/v1/chat/completions",
        model: str = "cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit",
        temperature: float = 0.7,
        max_tokens: int = 512,
        timeout: float = 60.0,
        system_prompt: str = "/no_think 你是一个友好、乐于助人的AI语音助手。请用简洁、自然的口语化方式回答用户的问题。不要输出任何思考过程，直接给出回答。",
    ):
        """
        Initialize LLM Handler

        Args:
            api_url: vLLM API endpoint
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            system_prompt: System prompt for the model
        """
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)

        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.system_prompt = system_prompt

        self.client = None
        self.conversation_history: List[Dict[str, str]] = []

    def setup(self):
        """Setup HTTP client and test connection"""
        try:
            logger.info(f"Setting up LLM handler with API: {self.api_url}")

            # Create HTTP client
            self.client = httpx.Client(timeout=self.timeout)

            # Initialize conversation with system prompt
            self.conversation_history = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Test connection
            health_url = self.api_url.replace('/v1/chat/completions', '/health')
            try:
                response = self.client.get(health_url, timeout=5.0)
                if response.status_code == 200:
                    logger.info("✓ vLLM Service is healthy and ready")
                else:
                    logger.warning(f"⚠️ vLLM Service health check returned {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Cannot connect to vLLM Service health endpoint: {e}")

            logger.info("✓ LLM Handler initialized")

        except Exception as e:
            logger.error(f"LLM setup failed: {e}", exc_info=True)
            raise

    def process(self, input_data):
        """
        Generate LLM response to user input

        Args:
            input_data: User text input (from STT)

        Returns:
            LLM generated response text
        """
        try:
            user_text = input_data

            if not user_text or not isinstance(user_text, str):
                logger.warning(f"Invalid LLM input: {user_text}")
                return None

            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_text
            })

            # Keep conversation history reasonable (last 10 turns)
            if len(self.conversation_history) > 21:  # 1 system + 20 messages
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-20:]

            logger.info(f"LLM input: '{user_text}'")

            # Call vLLM API
            response_text = self._call_vllm_api()

            if response_text:
                clean_text = _strip_markdown(response_text)

                # Store clean text in history (avoids re-reading markdown noise)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": clean_text
                })

                logger.info(f"✓ LLM output: '{clean_text[:100]}...'")

                if self.socketio:
                    self.socketio.emit('llm_message', {'text': clean_text})

                return clean_text

            return None

        except Exception as e:
            logger.error(f"LLM processing error: {e}", exc_info=True)
            return None

    def _call_vllm_api(self) -> str:
        """
        Call vLLM API for chat completion

        Returns:
            Generated response text
        """
        try:
            response = self.client.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": self.conversation_history,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": False,
                    # Disable Qwen3 thinking mode (vLLM top-level parameter)
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )

            response.raise_for_status()
            result = response.json()

            # Extract generated text
            generated_text = result["choices"][0]["message"]["content"]
            logger.debug(f"Raw LLM output (first 200): {generated_text[:200]!r}")

            # Strip <think>...</think> tags (standard format)
            generated_text = re.sub(r'<think>.*?</think>', '', generated_text, flags=re.DOTALL)

            # Strip "Thinking Process" style blocks - extract only the final answer
            cleaned = _extract_answer(generated_text)

            return cleaned.strip()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling vLLM API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Failed to call vLLM API: {e}")
            raise

    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ]
        logger.info("Conversation history reset")

    def cleanup(self):
        """Close HTTP client"""
        if self.client:
            self.client.close()
