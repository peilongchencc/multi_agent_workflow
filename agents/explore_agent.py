"""探索型子 Agent — 专注于文件系统探索和信息收集。

配备只读文件工具（read_file, list_directory, search_files）
以及联网工具（web_search, web_parser），能够探索工作空间并检索网络信息。
"""
from agents.base import BaseAgent
from config import DASHSCOPE_API_KEY
from prompts import EXPLORE_AGENT_PROMPT
from tools.file_tools import ListDirectoryTool, ReadFileTool, SearchFilesTool
from tools.registry import ToolRegistry
from tools.web_tools import WebParserTool, WebSearchTool


def create_explore_agent() -> BaseAgent:
    """创建探索型 Agent 实例。"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(ListDirectoryTool())
    registry.register(SearchFilesTool())

    if DASHSCOPE_API_KEY:
        registry.register(WebSearchTool())
        registry.register(WebParserTool())

    return BaseAgent(
        agent_type="explore",
        system_prompt=EXPLORE_AGENT_PROMPT,
        tool_registry=registry,
    )
