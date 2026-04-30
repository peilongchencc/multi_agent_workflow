"""Agent 工厂 — 根据任务类型创建对应的子 Agent 实例。"""
from agents.base import BaseAgent
from agents.code_agent import create_code_agent
from agents.explore_agent import create_explore_agent
from agents.shell_agent import create_shell_agent
from models import SubAgentType


_CREATORS = {
    SubAgentType.EXPLORE: create_explore_agent,
    SubAgentType.CODE: create_code_agent,
    SubAgentType.SHELL: create_shell_agent,
    SubAgentType.GENERAL: create_code_agent,
}


class AgentFactory:
    """根据 SubAgentType 创建对应的 Agent 实例。"""

    @staticmethod
    def create(agent_type: str) -> BaseAgent:
        """创建指定类型的 Agent。

        Args:
            agent_type: Agent 类型字符串，对应 SubAgentType 枚举值。

        Returns:
            对应类型的 BaseAgent 实例。

        Raises:
            ValueError: 未知的 Agent 类型。
        """
        try:
            enum_type = SubAgentType(agent_type)
        except ValueError:
            raise ValueError(
                f"未知的Agent类型: '{agent_type}'，"
                f"可选: {[t.value for t in SubAgentType]}"
            )

        creator = _CREATORS.get(enum_type)
        if not creator:
            raise ValueError(f"Agent类型 '{agent_type}' 未注册创建函数")

        return creator()
