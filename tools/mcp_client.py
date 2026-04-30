"""MCP HTTP 客户端，支持 Streamable HTTP 和 SSE 两种协议。

通过标准 MCP 协议调用阿里云百炼 MCP 服务，
实现 initialize → notifications/initialized → tools/call 的标准交互流程。
"""
import asyncio
import json

import aiohttp
from loguru import logger


class McpHttpClient:
    """MCP Streamable HTTP 客户端。

    Args:
        base_url: MCP Server 的 Streamable HTTP 端点（以 /mcp 结尾）。
        headers: 请求头（包含认证信息）。
    """

    def __init__(self, base_url: str, headers: dict[str, str]) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **headers,
        }
        self._session_id: str | None = None
        self._initialized = False

    async def _post(self, payload: dict, expect_response: bool = True) -> dict | None:
        """发送 HTTP POST 请求。"""
        headers = {**self._headers}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self._base_url, json=payload, headers=headers) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self._session_id = sid

                if not expect_response or resp.status == 202:
                    return None

                content_type = resp.content_type or ""
                raw_text = await resp.text()

                if resp.status != 200:
                    logger.error(f"MCP HTTP {resp.status}: {raw_text[:300]}")
                    raise RuntimeError(f"MCP 请求失败 ({resp.status}): {raw_text[:300]}")

                if "application/json" in content_type:
                    return json.loads(raw_text)

                return _parse_sse_response(raw_text)

    async def initialize(self) -> None:
        """执行 MCP 握手：initialize + notifications/initialized。"""
        if self._initialized:
            return

        result = await self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "multi-agent-workflow", "version": "1.0.0"},
            },
        })
        logger.debug(f"MCP initialize 响应: {str(result)[:200]}")

        await self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_response=False,
        )
        self._initialized = True
        logger.info(f"MCP 初始化完成: {self._base_url}")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP Server 上的工具。"""
        if not self._initialized:
            await self.initialize()

        data = await self._post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        return _extract_text(data)


class McpSseClient:
    """MCP SSE 客户端。

    用于不支持 Streamable HTTP 的 MCP Server（如百炼 WebParser）。
    SSE 流程: GET /sse 建立持久连接 → 获取 message endpoint
    → POST JSON-RPC 到 endpoint → 通过 SSE 流接收响应。

    Args:
        sse_url: MCP Server 的 SSE 端点（以 /sse 结尾）。
        headers: 请求头（包含认证信息）。
    """

    def __init__(self, sse_url: str, headers: dict[str, str]) -> None:
        self._sse_url = sse_url.rstrip("/")
        self._headers = headers
        self._message_endpoint: str | None = None
        self._response_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._session: aiohttp.ClientSession | None = None
        self._sse_task: asyncio.Task | None = None
        self._initialized = False

    async def _start_sse_listener(self) -> None:
        """启动 SSE 监听，维持持久连接并读取响应。"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=300),
        )
        resp = await self._session.get(self._sse_url, headers=self._headers)

        if resp.status != 200:
            raw = await resp.text()
            raise RuntimeError(f"SSE 连接失败 ({resp.status}): {raw[:200]}")

        async def reader():
            buffer = ""
            current_event = ""
            try:
                async for chunk_bytes in resp.content.iter_any():
                    buffer += chunk_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            if current_event == "endpoint":
                                if data_str.startswith("http"):
                                    self._message_endpoint = data_str
                                elif data_str.startswith("/"):
                                    base = self._sse_url.split("/api/")[0]
                                    self._message_endpoint = base + data_str
                                logger.debug(f"SSE endpoint: {self._message_endpoint}")
                            elif data_str:
                                try:
                                    parsed = json.loads(data_str)
                                    if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                                        await self._response_queue.put(parsed)
                                except json.JSONDecodeError:
                                    pass
                            current_event = ""
                        elif not line:
                            current_event = ""
            except (asyncio.CancelledError, aiohttp.ClientError):
                pass

        self._sse_task = asyncio.create_task(reader())

        for _ in range(50):
            if self._message_endpoint:
                return
            await asyncio.sleep(0.1)

        raise RuntimeError("SSE 未在 5 秒内返回 message endpoint")

    async def _post_and_wait(self, payload: dict, wait_response: bool = True) -> dict | None:
        """POST 到 message endpoint，并从 SSE 流等待响应。"""
        if not self._message_endpoint:
            await self._start_sse_listener()

        headers = {
            "Content-Type": "application/json",
            **self._headers,
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self._message_endpoint, json=payload, headers=headers) as resp:
                if resp.status not in (200, 202):
                    raw = await resp.text()
                    raise RuntimeError(f"MCP POST 失败 ({resp.status}): {raw[:200]}")

        if not wait_response:
            return None

        try:
            return await asyncio.wait_for(self._response_queue.get(), timeout=60)
        except asyncio.TimeoutError:
            raise RuntimeError("MCP SSE 响应超时 (30s)")

    async def initialize(self) -> None:
        """执行 MCP 握手。"""
        if self._initialized:
            return

        result = await self._post_and_wait({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "multi-agent-workflow", "version": "1.0.0"},
            },
        })
        logger.debug(f"MCP SSE initialize 响应: {str(result)[:200]}")

        await self._post_and_wait(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            wait_response=False,
        )
        self._initialized = True
        logger.info(f"MCP SSE 初始化完成: {self._sse_url}")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP Server 上的工具。"""
        if not self._initialized:
            await self.initialize()

        data = await self._post_and_wait({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        return _extract_text(data)

    async def close(self) -> None:
        """关闭 SSE 连接。"""
        if self._sse_task:
            self._sse_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()


def _parse_sse_response(raw: str) -> dict:
    """从 SSE 流中提取最后一个有效 JSON-RPC 响应。"""
    last_data: dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                parsed = json.loads(data_str)
                if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                    last_data = parsed
            except json.JSONDecodeError:
                continue
    return last_data


def _extract_text(data: dict | None) -> str:
    """从 MCP 响应中提取文本内容。"""
    if data is None:
        return "(MCP 服务未返回结果)"

    if "error" in data:
        error_msg = data["error"].get("message", str(data["error"]))
        raise RuntimeError(f"MCP 工具调用错误: {error_msg}")

    result = data.get("result", data)
    if isinstance(result, dict) and "content" in result:
        parts = []
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item["text"])
        return "\n".join(parts) if parts else str(result)

    return str(result)
