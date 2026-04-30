"""任务调度器 — 工作流 Stage 2。

负责使用 LLM 将任务拆解为子任务，并解析依赖关系生成执行计划。
支持同层任务并行执行、跨层任务串行执行。
"""
from loguru import logger

from core.intent_parser import IntentParseResult
from llm_client import llm_client
from models import SubTask, TaskPlan, WorkflowContext
from prompts import TASK_PLAN_PROMPT


class TaskScheduler:
    """任务规划与调度。"""

    async def plan(
        self,
        context: WorkflowContext,
        intent: IntentParseResult,
    ) -> TaskPlan:
        """使用 LLM 将用户任务拆解为子任务。

        Args:
            context: 工作流上下文。
            intent: 意图解析结果。

        Returns:
            包含子任务列表的 TaskPlan。
        """
        user_msg = (
            f"用户输入: {context.user_input}\n\n"
            f"意图分析:\n"
            f"- 模式: {intent.mode.value}\n"
            f"- 所需Agent: {[a.value for a in intent.required_agents]}\n"
            f"- 分析: {intent.reasoning}\n\n"
            f"工作空间目录:\n{context.directory_tree or '(空)'}"
        )
        messages = [
            {"role": "system", "content": TASK_PLAN_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        logger.info("[task-scheduler] 开始任务规划...")
        result = await llm_client.chat_completion_json(messages, temperature=0.3)

        sub_tasks = [
            SubTask(
                id=t["id"],
                description=t["description"],
                agent_type=t["agent_type"],
                dependencies=t.get("dependencies", []),
            )
            for t in result.get("sub_tasks", [])
        ]

        plan = TaskPlan(
            mode=intent.mode,
            reasoning=intent.reasoning,
            sub_tasks=sub_tasks,
        )

        logger.info(f"[task-scheduler] 规划完成，共 {len(sub_tasks)} 个子任务:")
        for t in sub_tasks:
            deps = f" (依赖: {t.dependencies})" if t.dependencies else ""
            logger.info(f"  [{t.agent_type}] {t.id}: {t.description}{deps}")

        return plan

    @staticmethod
    def resolve_execution_order(plan: TaskPlan) -> list[list[str]]:
        """解析任务依赖，生成分层并行执行顺序。

        同一层内的任务无互相依赖，可并行执行；
        不同层之间串行执行，后层依赖前层的结果。

        Args:
            plan: 任务计划。

        Returns:
            分层任务ID列表。例如 [["task_1", "task_2"], ["task_3"]]
            表示 task_1 和 task_2 并行执行，完成后再执行 task_3。
        """
        task_map = {t.id: t for t in plan.sub_tasks}
        completed: set[str] = set()
        remaining = set(task_map.keys())
        layers: list[list[str]] = []

        while remaining:
            current_layer = [
                tid
                for tid in remaining
                if all(dep in completed for dep in task_map[tid].dependencies)
            ]

            if not current_layer:
                logger.warning("[task-scheduler] 检测到循环依赖，强制执行剩余任务")
                current_layer = list(remaining)

            layers.append(current_layer)
            completed.update(current_layer)
            remaining -= set(current_layer)

        logger.info(f"[task-scheduler] 执行顺序: {layers}")
        return layers
