"""
CodexBackend —— 用 `codex exec` 子进程驱动对话。

- 新会话:  codex exec --json -s read-only --skip-git-repo-check -C <workspace> -o <out> "<text>"
            从 stdout 的 {"type":"thread.started","thread_id":...} 拿到 thread_id
- 续接:    codex exec resume <thread_id> --json --skip-git-repo-check -o <out> "<text>"
            (工作目录/沙箱由原会话继承)
- 最终回复从 -o 文件读取(最干净)。turn.failed/error 事件 → 记录并兜底。

注意:依赖归一化代理 (codex_vllm_proxy.py) 已在 .codex_home/config.toml 指向的
端口上运行。Codex CLI 需要 node 在 PATH 上。

v2 优化点:换成 codex app-server 常驻进程可消除每轮子进程启动开销。
"""

import os
import json
import shutil
import logging
import tempfile
import subprocess
from typing import Optional

from .base import AgentBackend, AgentResult

logger = logging.getLogger(__name__)


class CodexError(RuntimeError):
    pass


class CodexBackend(AgentBackend):
    def __init__(
        self,
        codex_home: str,
        workspace: str,
        codex_bin: str = "codex",
        node_bin_dir: Optional[str] = None,
        sandbox: str = "read-only",
        timeout: float = 150.0,
    ):
        self.codex_home = os.path.abspath(codex_home)
        self.workspace = os.path.abspath(workspace)
        self.codex_bin = codex_bin
        self.node_bin_dir = node_bin_dir
        self.sandbox = sandbox
        self.timeout = timeout

    # -- env ---------------------------------------------------------------
    def _env(self) -> dict:
        env = os.environ.copy()
        env["CODEX_HOME"] = self.codex_home
        if self.node_bin_dir:
            env["PATH"] = self.node_bin_dir + os.pathsep + env.get("PATH", "")
        return env

    def verify(self):
        """启动时自检:codex 可执行 + node 在 PATH。"""
        env = self._env()
        bin_path = shutil.which(self.codex_bin, path=env.get("PATH"))
        if not bin_path:
            raise CodexError(f"找不到 codex 可执行文件 (PATH={env.get('PATH','')[:80]}...)")
        try:
            r = subprocess.run([self.codex_bin, "--version"], env=env,
                               capture_output=True, text=True, timeout=10)
            logger.info("Codex CLI: %s", r.stdout.strip() or r.stderr.strip())
        except Exception as e:
            raise CodexError(f"codex --version 失败: {e}")

    # -- chat --------------------------------------------------------------
    def chat(self, thread_id: Optional[str], user_text: str) -> AgentResult:
        out_fd, out_path = tempfile.mkstemp(prefix="codex_out_", suffix=".txt")
        os.close(out_fd)
        try:
            if thread_id:
                cmd = [self.codex_bin, "exec", "resume", thread_id,
                       "--json", "--skip-git-repo-check", "-o", out_path, user_text]
            else:
                cmd = [self.codex_bin, "exec",
                       "--json", "-s", self.sandbox, "--skip-git-repo-check",
                       "-C", self.workspace, "-o", out_path, user_text]

            proc = subprocess.run(
                cmd, env=self._env(), cwd=self.workspace,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=self.timeout,
            )

            new_tid = thread_id
            fail_msg = None
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type")
                if etype == "thread.started":
                    new_tid = ev.get("thread_id") or new_tid
                elif etype in ("turn.failed", "error"):
                    err = ev.get("error") or ev.get("message")
                    fail_msg = err.get("message") if isinstance(err, dict) else str(err)

            answer = ""
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    answer = f.read().strip()
            except Exception:
                pass

            if not answer:
                if fail_msg:
                    logger.error("Codex turn failed: %s", str(fail_msg)[:200])
                else:
                    logger.error("Codex empty answer (rc=%s) stderr=%s",
                                 proc.returncode, proc.stderr[-200:])
                raise CodexError(fail_msg or "codex 无回复")

            return AgentResult(answer=answer, thread_id=new_tid or "")
        finally:
            try:
                os.remove(out_path)
            except OSError:
                pass
