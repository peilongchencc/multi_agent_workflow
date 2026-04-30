"""意图解析器 — 工作流 Stage 1 的后半部分。

使用 LLM 分析用户输入，判断工作模式和所需的子 Agent 类型。
"""
from dataclasses import dataclass, field

from loguru import logger

from llm_client import llm_client
from models import AgentMode, SubAgentType, WorkflowContext
from prompts import INTENT_PARSE_PROMPT


@dataclass
class IntentParseResult:
    """意图解析结果。"""
    mode: AgentMode
    required_agents: list[SubAgentType] = field(default_factory=list)
    reasoning: str = ""


class IntentParser:
    """使用 LLM 解析用户意图，完成模式路由。"""

    async def parse(self, context: WorkflowContext) -> IntentParseResult:
        """解析用户意图。

        Args:
            context: 工作流上下文。

        Returns:
            意图解析结果，包含模式、所需Agent类型和推理过程。
        """
        user_msg = self._build_analysis_input(context)
        messages = [
            {"role": "system", "content": INTENT_PARSE_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        logger.info("[intent-parser] 开始意图解析...")
        result = await llm_client.chat_completion_json(messages, temperature=0.3)

        mode = AgentMode(result.get("mode", "agent"))
        required_agents = [
            SubAgentType(a) for a in result.get("required_agents", ["general"])
        ]
        reasoning = result.get("reasoning", "")

        logger.info(
            f"[intent-parser] 解析完成 | "
            f"模式={mode.value} | "
            f"所需Agent={[a.value for a in required_agents]}"
        )
        logger.info(f"[intent-parser] 推理: {reasoning}")

        return IntentParseResult(
            mode=mode,
            required_agents=required_agents,
            reasoning=reasoning,
        )

    @staticmethod
    def _build_analysis_input(context: WorkflowContext) -> str:
        """将上下文组装为 LLM 可理解的分析输入。"""
        loaded_files = list(context.file_contents.keys()) if context.file_contents else []
        return (
            f"用户输入: {context.user_input}\n\n"
            f"工作空间路径: {context.workspace_path}\n"
            f"目录结构:\n{context.directory_tree or '(空工作空间)'}\n\n"
            f"已加载文件: {loaded_files or '无'}"
        )
