"""
Agent 后端抽象。

把"对话大脑"抽象成一个接口,这样上层 handler 不关心底层是 Codex 子进程、
Codex app-server,还是将来换成 Claude / 直连 vLLM。

约定:
- chat(thread_id, user_text) 接收上一轮的 thread_id(None 表示新会话),
  返回回复文本 + (新)thread_id。上层负责持久化 thread_id ↔ client_id 映射。
"""

from abc import ABC, abstractmethod
from typing import NamedTuple, Optional


class AgentResult(NamedTuple):
    answer: str
    thread_id: str


class AgentBackend(ABC):
    @abstractmethod
    def chat(self, thread_id: Optional[str], user_text: str) -> AgentResult:
        """thread_id=None → 新建会话;否则在该会话上续接。"""
        raise NotImplementedError
