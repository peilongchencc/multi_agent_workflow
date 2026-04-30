"""工具注册表与基类，管理所有可供 Agent 调用的工具。"""
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """工具基类，所有工具必须继承此类。

    Attributes:
        name: 工具唯一标识名。
        description: 工具功能描述，供 LLM 理解。
        parameters: JSON Schema 格式的参数定义。
    """
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具逻辑。"""
        ...

    def to_openai_tool(self) -> dict:
        """转换为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表，管理一组工具并提供查找能力。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """列出所有已注册工具的名称。"""
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict]:
        """将所有工具转换为 OpenAI function calling 格式列表。"""
        return [t.to_openai_tool() for t in self._tools.values()]
