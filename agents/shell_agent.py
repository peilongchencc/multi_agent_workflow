"""Shell 型子 Agent — 专注于命令行操作。

配备命令执行工具和文件读取工具，
能够运行脚本、安装依赖、查看运行结果。
"""
from agents.base import BaseAgent
from prompts import SHELL_AGENT_PROMPT
from tools.file_tools import ReadFileTool
from tools.registry import ToolRegistry
from tools.shell_tools import ExecuteCommandTool


def create_shell_agent() -> BaseAgent:
    """创建 Shell 型 Agent 实例。"""
    registry = ToolRegistry()
    registry.register(ExecuteCommandTool())
    registry.register(ReadFileTool())

    return BaseAgent(
        agent_type="shell",
        system_prompt=SHELL_AGENT_PROMPT,
        tool_registry=registry,
    )
