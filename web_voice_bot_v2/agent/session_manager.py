"""
会话管理器 —— 多用户接口的核心。

把 client_id 映射到 Codex thread_id,并持久化到磁盘:
- 服务器重启后,映射还在,配合 .codex_home/sessions 里的会话文件,
  可以 resume 回同一个 thread(记忆不丢)。
- 页面刷新不影响:thread 活在服务端,与浏览器连接无关。

单用户现在用 DEFAULT_CLIENT_ID;将来多用户时,前端用 localStorage 里固定的
UUID 作为 client_id 传入即可,无需改这里。
"""

import os
import json
import logging
from threading import Lock
from typing import Optional, Dict

logger = logging.getLogger(__name__)

DEFAULT_CLIENT_ID = "default"


class SessionManager:
    def __init__(self, persist_path: str):
        self.persist_path = persist_path
        self._lock = Lock()
        self._map: Dict[str, str] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, "r", encoding="utf-8") as f:
                    self._map = json.load(f)
                logger.info("Loaded %d session(s) from %s", len(self._map), self.persist_path)
        except Exception as e:
            logger.warning("Failed to load sessions: %s", e)
            self._map = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            tmp = self.persist_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._map, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.persist_path)
        except Exception as e:
            logger.warning("Failed to save sessions: %s", e)

    def get(self, client_id: str = DEFAULT_CLIENT_ID) -> Optional[str]:
        with self._lock:
            return self._map.get(client_id)

    def set(self, client_id: str, thread_id: str):
        with self._lock:
            if thread_id and self._map.get(client_id) != thread_id:
                self._map[client_id] = thread_id
                self._save()

    def reset(self, client_id: str = DEFAULT_CLIENT_ID):
        """清掉该 client 的 thread → 下次对话开新会话(忘记历史)。"""
        with self._lock:
            if client_id in self._map:
                del self._map[client_id]
                self._save()
                logger.info("Reset session for client_id=%s", client_id)
