"""异步 LLM API 客户端，基于 aiohttp，兼容 OpenAI API 格式。"""
import json

import aiohttp
from loguru import logger

from config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
)


class LLMClient:
    """异步 LLM 客户端，支持普通对话和工具调用。"""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """懒初始化 aiohttp session。"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=120),
            )
        return self._session

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """调用 Chat Completion API。

        Args:
            messages: 对话消息列表。
            tools: OpenAI function calling 格式的工具定义。
            temperature: 温度参数，控制输出随机性。
            max_tokens: 最大生成 token 数。
            response_format: 响应格式约束（如 JSON 模式）。

        Returns:
            LLM 响应的 message 字典，包含 content 和可选的 tool_calls。
        """
        session = await self._get_session()
        payload: dict = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": temperature if temperature is not None else LLM_TEMPERATURE,
            "max_tokens": max_tokens or LLM_MAX_TOKENS,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format

        url = f"{LLM_BASE_URL}/chat/completions"
        logger.debug(f"LLM 请求 -> model={LLM_MODEL}, messages={len(messages)}")

        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"LLM API 错误: {resp.status} - {error_text[:500]}")
                raise RuntimeError(f"LLM API 返回 {resp.status}: {error_text[:500]}")
            data = await resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        logger.debug(f"LLM 响应 <- finish_reason={choice['finish_reason']}")
        return message

    async def chat_completion_json(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> dict:
        """调用 LLM 并将响应解析为 JSON。

        内部使用 response_format=json_object 确保输出为合法 JSON。
        """
        message = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = message.get("content", "{}")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败，尝试修复: {e}")
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
            raise

    async def close(self):
        """关闭 HTTP session。"""
        if self._session and not self._session.closed:
            await self._session.close()


# 全局单例
llm_client = LLMClient()
