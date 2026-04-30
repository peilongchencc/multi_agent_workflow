"""代码型子 Agent — 专注于代码编写和文件修改。

配备完整的文件操作工具（read, write, list, search），
能够读取现有代码、编写新代码、修改文件。
"""
from agents.base import BaseAgent
from prompts import CODE_AGENT_PROMPT
from tools.file_tools import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from tools.registry import ToolRegistry


def create_code_agent() -> BaseAgent:
    """创建代码型 Agent 实例。"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirectoryTool())
    registry.register(SearchFilesTool())

    return BaseAgent(
        agent_type="code",
        system_prompt=CODE_AGENT_PROMPT,
        tool_registry=registry,
    )
