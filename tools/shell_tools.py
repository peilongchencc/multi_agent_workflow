"""Shell 命令执行工具，提供安全的命令行操作能力。"""
import asyncio
import os
from typing import Any

from config import WORKSPACE_DIR
from tools.registry import BaseTool


class ExecuteCommandTool(BaseTool):
    """在工作空间目录下执行 Shell 命令。"""

    name = "execute_command"
    description = "在工作空间目录下执行Shell命令并返回输出"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的Shell命令"},
        },
        "required": ["command"],
    }

    _BLOCKED_PATTERNS = [
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=/dev",
        ":(){",
        "> /dev/sda",
    ]
    _TIMEOUT_SECONDS = 30

    async def execute(self, command: str, **_: Any) -> str:
        for blocked in self._BLOCKED_PATTERNS:
            if blocked in command:
                return f"错误: 命令被安全策略阻止 (包含危险操作 '{blocked}')"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_DIR.resolve()),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return f"错误: 命令执行超时 ({self._TIMEOUT_SECONDS}秒)"
        except Exception as e:
            return f"错误: 命令执行失败 - {e}"

        parts: list[str] = []
        if stdout:
            parts.append(f"[stdout]\n{stdout.decode('utf-8', errors='replace')}")
        if stderr:
            parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")
        output = "\n".join(parts) if parts else "(无输出)"

        status = "成功" if proc.returncode == 0 else f"失败 (exit_code={proc.returncode})"
        return f"命令执行{status}:\n{output}"
