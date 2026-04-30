"""Agent 基类 — 工作流 Stage 3-4 的执行引擎。

实现 "工具路由 + 参数推理 → 执行 → 观察 → 修正" 的核心循环。
这是 Agent 区别于普通 LLM 调用的关键：不是单次调用，而是
反复的 ReAct 循环直到任务完成。
"""
import json
from typing import Any

from loguru import logger

from config import MAX_AGENT_ITERATIONS
from llm_client import llm_client
from models import AgentStep
from tools.registry import ToolRegistry


class BaseAgent:
    """所有子 Agent 的基类。

    通过 LLM function calling 驱动工具调用循环：
    1. LLM 根据当前对话上下文选择要调用的工具（工具路由 + 参数推理）
    2. 执行工具并将结果返回给 LLM（执行 + 观察）
    3. LLM 判断是否需要继续调用工具（修正/完成）
    4. 重复直到 LLM 返回最终文本响应
    """

    def __init__(
        self,
        agent_type: str,
        system_prompt: str,
        tool_registry: ToolRegistry,
    ):
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry
        self.steps: list[AgentStep] = []

    async def run(self, task_description: str, context: str = "") -> str:
        """执行任务。

        Args:
            task_description: 任务描述。
            context: 来自前置任务的上下文信息。

        Returns:
            Agent 的最终文本回复。
        """
        user_content = task_description
        if context:
            user_content += f"\n\n--- 前置任务结果 ---\n{context}"

        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]
        tools = self.tool_registry.to_openai_tools()

        logger.info(
            f"[{self.agent_type}] 启动 | 可用工具: {self.tool_registry.list_names()}"
        )

        for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
            logger.info(f"[{self.agent_type}] --- 迭代 {iteration}/{MAX_AGENT_ITERATIONS} ---")

            response = await llm_client.chat_completion(
                messages=messages,
                tools=tools if tools else None,
            )

            tool_calls = response.get("tool_calls")
            content = response.get("content", "")

            if not tool_calls:
                logger.info(f"[{self.agent_type}] 任务完成，生成最终回复")
                self._record_step("完成", {"response_preview": content[:200]})
                return content

            # LLM 选择了工具调用 → 进入 执行→观察 阶段
            messages.append(response)
            for tc in tool_calls:
                result_str = await self._execute_tool_call(tc)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

        final = f"[{self.agent_type}] 达到最大迭代次数({MAX_AGENT_ITERATIONS})，强制结束"
        logger.warning(final)
        return final

    async def _execute_tool_call(self, tool_call: dict) -> str:
        """执行单个工具调用。

        对应工作流中的 "工具路由 + 参数推理 → 执行" 环节，
        LLM 已经完成了路由和参数推理，这里负责实际执行。
        """
        func_info = tool_call["function"]
        tool_name = func_info["name"]

        try:
            arguments = json.loads(func_info.get("arguments", "{}"))
        except json.JSONDecodeError:
            err = f"工具参数JSON解析失败: {func_info.get('arguments', '')[:200]}"
            logger.error(f"[{self.agent_type}] {err}")
            return err

        tool = self.tool_registry.get(tool_name)
        if not tool:
            err = f"未知工具 '{tool_name}'，可用: {self.tool_registry.list_names()}"
            logger.error(f"[{self.agent_type}] {err}")
            return err

        logger.info(f"[{self.agent_type}] 工具调用: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")

        try:
            result = await tool.execute(**arguments)
            result_str = str(result)
            self._record_step(f"工具调用: {tool_name}", {
                "arguments": arguments,
                "result_preview": result_str[:300],
            })
            logger.info(
                f"[{self.agent_type}] 工具结果 ({len(result_str)} 字符): "
                f"{result_str[:150]}{'...' if len(result_str) > 150 else ''}"
            )
            return result_str
        except Exception as e:
            err = f"工具执行异常: {type(e).__name__}: {e}"
            logger.error(f"[{self.agent_type}] {err}")
            self._record_step(f"工具异常: {tool_name}", {"error": str(e)})
            return err

    def _record_step(self, action: str, detail: Any = None) -> None:
        """记录执行步骤，用于最终结果追溯。"""
        self.steps.append(AgentStep(
            stage="execution",
            agent_type=self.agent_type,
            action=action,
            detail=detail,
        ))
