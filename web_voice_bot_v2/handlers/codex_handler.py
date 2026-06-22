"""
Codex Handler —— 替换 LLMHandler。

管线位置不变:STT → CodexHandler → TTS。
内部用 Codex(跑在本地 vLLM 上)提供对话 + 跨轮记忆(Codex thread)。

记忆/会话:
- thread 活在服务端(.codex_home/sessions),浏览器刷新不影响。
- client_id → thread_id 由 SessionManager 持久化,服务器重启可 resume。
- 单用户现在用 DEFAULT_CLIENT_ID;多用户时把 (client_id, text) 作为 input 传入即可。
"""

import os
import sys
import logging
from threading import Event
from queue import Queue
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_handler import BaseHandler
from agent.codex_backend import CodexBackend, CodexError
from agent.session_manager import SessionManager, DEFAULT_CLIENT_ID
from agent.text_utils import strip_markdown, strip_thinking

logger = logging.getLogger(__name__)

_FALLBACK = "抱歉，我这边出了点问题，可以再说一遍吗？"


class CodexHandler(BaseHandler):
    def __init__(
        self,
        stop_event: Event,
        queue_in: Queue,
        queue_out: Queue,
        setup_args=(),
        setup_kwargs=None,
        codex_home: str = None,
        workspace: str = None,
        sessions_path: str = None,
        node_bin_dir: Optional[str] = None,
        timeout: float = 150.0,
    ):
        super().__init__(stop_event, queue_in, queue_out, setup_args, setup_kwargs)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.codex_home = codex_home or os.path.join(base, ".codex_home")
        self.workspace = workspace or os.path.join(self.codex_home, "workspace")
        self.sessions_path = sessions_path or os.path.join(base, "data", "sessions.json")
        self.node_bin_dir = node_bin_dir
        self.timeout = timeout

        self.backend: Optional[CodexBackend] = None
        self.sessions: Optional[SessionManager] = None

    def setup(self):
        logger.info("Setting up Codex handler (home=%s)", self.codex_home)
        self.backend = CodexBackend(
            codex_home=self.codex_home,
            workspace=self.workspace,
            node_bin_dir=self.node_bin_dir,
            timeout=self.timeout,
        )
        self.backend.verify()
        self.sessions = SessionManager(self.sessions_path)
        logger.info("✓ Codex handler ready")

    @staticmethod
    def _parse(input_data) -> Tuple[str, str]:
        """兼容 str(单用户) 与 {'client_id','text'}(未来多用户)。"""
        if isinstance(input_data, dict):
            return input_data.get("client_id", DEFAULT_CLIENT_ID), input_data.get("text", "")
        return DEFAULT_CLIENT_ID, input_data

    def process(self, input_data):
        client_id, user_text = self._parse(input_data)
        if not user_text or not isinstance(user_text, str):
            logger.warning("Invalid Codex input: %r", input_data)
            return None

        logger.info("Codex input (client=%s): %r", client_id, user_text)
        thread_id = self.sessions.get(client_id)

        try:
            result = self.backend.chat(thread_id, user_text)
        except CodexError as e:
            logger.error("Codex chat error: %s", e)
            if self.socketio:
                self.socketio.emit("llm_message", {"text": _FALLBACK})
            return _FALLBACK
        except Exception as e:
            logger.error("Codex unexpected error: %s", e, exc_info=True)
            if self.socketio:
                self.socketio.emit("llm_message", {"text": _FALLBACK})
            return _FALLBACK

        # 持久化(可能是新建的 thread)
        if result.thread_id:
            self.sessions.set(client_id, result.thread_id)

        clean = strip_markdown(strip_thinking(result.answer))
        if not clean:
            clean = _FALLBACK

        logger.info("✓ Codex output: %r", clean[:100])
        if self.socketio:
            self.socketio.emit("llm_message", {"text": clean})
        return clean

    def reset_session(self, client_id: str = DEFAULT_CLIENT_ID):
        if self.sessions:
            self.sessions.reset(client_id)
