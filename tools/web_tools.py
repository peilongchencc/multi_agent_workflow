"""联网搜索和网页解析工具，通过阿里云百炼 MCP 服务实现。

让 Agent 具备实时联网搜索和网页内容解析能力，
用于回答需要最新信息的问题。
"""
from typing import Any

from loguru import logger

from config import DASHSCOPE_API_KEY, WEBPARSER_MCP_URL, WEBSEARCH_MCP_URL
from tools.mcp_client import McpHttpClient, McpSseClient
from tools.registry import BaseTool


class WebSearchTool(BaseTool):
    """通过阿里云百炼 MCP 进行联网搜索。"""

    name = "web_search"
    description = "联网搜索实时信息，适用于需要最新资料、新闻、技术文档等场景"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        self._client = McpHttpClient(
            base_url=WEBSEARCH_MCP_URL,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"},
        )

    async def execute(self, query: str, **_: Any) -> str:
        logger.info(f"[web_search] 搜索: {query}")
        try:
            result = await self._client.call_tool(
                "bailian_web_search", {"query": query, "count": 5},
            )
            if not result or result.strip() == "":
                return f"联网搜索 '{query}' 未返回有效结果"
            return f"联网搜索 '{query}' 的结果:\n{result}"
        except Exception as e:
            logger.error(f"[web_search] 搜索失败: {e}")
            return f"联网搜索失败: {e}"


class WebParserTool(BaseTool):
    """通过阿里云百炼 MCP 解析网页内容。"""

    name = "web_parser"
    description = "解析指定URL的网页内容，获取网页的文本信息"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要解析的网页URL（需以 http:// 或 https:// 开头）",
            },
        },
        "required": ["url"],
    }

    def __init__(self) -> None:
        self._client = McpSseClient(
            sse_url=WEBPARSER_MCP_URL,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"},
        )

    async def execute(self, url: str, **_: Any) -> str:
        logger.info(f"[web_parser] 解析网页: {url}")
        try:
            result = await self._client.call_tool("bailian_web_parser", {"url": url})
            if not result or result.strip() == "":
                return f"网页 '{url}' 未返回有效内容"
            max_len = 5000
            if len(result) > max_len:
                result = result[:max_len] + f"\n\n...(内容已截断，共 {len(result)} 字符)"
            return f"网页 '{url}' 的内容:\n{result}"
        except Exception as e:
            logger.error(f"[web_parser] 解析失败: {e}")
            return f"网页解析失败: {e}"
