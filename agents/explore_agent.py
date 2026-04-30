"""探索型子 Agent — 专注于文件系统探索和信息收集。

只配备只读工具（read_file, list_directory, search_files），
不具备写入能力，安全地探索工作空间。
"""
from agents.base import BaseAgent
from prompts import EXPLORE_AGENT_PROMPT
from tools.file_tools import ListDirectoryTool, ReadFileTool, SearchFilesTool
from tools.registry import ToolRegistry


def create_explore_agent() -> BaseAgent:
    """创建探索型 Agent 实例。"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(ListDirectoryTool())
    registry.register(SearchFilesTool())

    return BaseAgent(
        agent_type="explore",
        system_prompt=EXPLORE_AGENT_PROMPT,
        tool_registry=registry,
    )
