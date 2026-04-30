"""主工作流管线 — 串联 5 个阶段的完整流程。

Stage 1: 上下文组装 + 意图解析 + 模式路由
Stage 2: 任务规划与调度
Stage 3-4: 工具路由 + 参数推理 + 任务执行（执行→观察→修正循环）
Stage 5: 结果汇总 + 响应生成 + 状态同步
"""
import asyncio
import uuid

from loguru import logger

from agents.factory import AgentFactory
from core.context_builder import ContextBuilder
from core.intent_parser import IntentParser
from core.task_scheduler import TaskScheduler
from llm_client import llm_client
from models import (
    AgentStep,
    ChatRequest,
    ChatResponse,
    SubTask,
    TaskPlan,
    TaskStatus,
)
from prompts import RESULT_AGGREGATE_PROMPT


class WorkflowPipeline:
    """多 Agent 协同工作流管线。"""

    def __init__(self):
        self.context_builder = ContextBuilder()
        self.intent_parser = IntentParser()
        self.task_scheduler = TaskScheduler()

    async def run(self, request: ChatRequest) -> ChatResponse:
        """执行完整的多 Agent 协同工作流。

        Args:
            request: 用户聊天请求。

        Returns:
            包含最终结果和工作流详情的响应。
        """
        request_id = str(uuid.uuid4())
        steps: list[AgentStep] = []

        logger.info(f"{'='*20} 工作流开始 [request_id={request_id}] {'='*20}")

        # --- Stage 1: 上下文组装 + 意图解析 + 模式路由 ---
        logger.info("[Stage 1/5] 上下文组装 + 意图解析 + 模式路由")

        context = await self.context_builder.build(
            user_input=request.message,
            workspace_path=request.workspace_path,
            include_files=request.include_files,
        )
        steps.append(AgentStep(stage="context", action="上下文构建完成", detail={
            "workspace": context.workspace_path,
            "directory_tree": context.directory_tree[:300] if context.directory_tree else "(空)",
            "files_loaded": list(context.file_contents.keys()),
        }))

        intent = await self.intent_parser.parse(context)
        steps.append(AgentStep(stage="intent", action="意图解析完成", detail={
            "mode": intent.mode.value,
            "required_agents": [a.value for a in intent.required_agents],
            "reasoning": intent.reasoning,
        }))

        # --- Stage 2: 任务规划与调度 ---
        logger.info("[Stage 2/5] 任务规划与调度")

        plan = await self.task_scheduler.plan(context, intent)
        execution_order = self.task_scheduler.resolve_execution_order(plan)
        steps.append(AgentStep(stage="planning", action="任务规划完成", detail={
            "task_count": len(plan.sub_tasks),
            "execution_order": execution_order,
        }))

        # --- Stage 3-4: 工具路由 + 参数推理 + 任务执行 ---
        logger.info("[Stage 3-4/5] 工具路由 + 参数推理 + 任务执行")

        task_results: dict[str, str] = {}
        for layer_idx, layer in enumerate(execution_order, 1):
            logger.info(f"  -- 执行层 {layer_idx}/{len(execution_order)}: {layer} --")
            layer_steps = await self._execute_layer(plan, layer, task_results)
            steps.extend(layer_steps)

        # --- Stage 5: 结果汇总 + 响应生成 ---
        logger.info("[Stage 5/5] 结果汇总 + 响应生成")

        final_response = await self._aggregate_results(
            context.user_input, plan, task_results
        )
        steps.append(AgentStep(stage="aggregation", action="结果汇总完成"))

        logger.info(f"{'='*20} 工作流完成 [request_id={request_id}] {'='*20}")

        return ChatResponse(
            code=200,
            message="success",
            request_id=request_id,
            data={
                "response": final_response,
                "workflow_steps": [s.model_dump() for s in steps],
                "task_plan": plan.model_dump(),
            },
        )

    async def _execute_layer(
        self,
        plan: TaskPlan,
        layer: list[str],
        task_results: dict[str, str],
    ) -> list[AgentStep]:
        """执行同一层的所有任务（并行）。"""
        steps: list[AgentStep] = []
        coros = []
        task_ids = []

        for task_id in layer:
            sub_task = next(t for t in plan.sub_tasks if t.id == task_id)
            dep_context = self._build_dependency_context(sub_task, task_results)
            coros.append(self._run_sub_task(sub_task, dep_context))
            task_ids.append(task_id)

        results = await asyncio.gather(*coros, return_exceptions=True)

        for task_id, result in zip(task_ids, results):
            sub_task = next(t for t in plan.sub_tasks if t.id == task_id)
            if isinstance(result, Exception):
                sub_task.status = TaskStatus.FAILED
                sub_task.result = str(result)
                task_results[task_id] = f"执行失败: {result}"
                logger.error(f"  任务 {task_id} 失败: {result}")
            else:
                sub_task.status = TaskStatus.COMPLETED
                sub_task.result = result
                task_results[task_id] = result
                logger.info(f"  任务 {task_id} 完成 ({len(result)} 字符)")

            steps.append(AgentStep(
                stage="execution",
                agent_type=sub_task.agent_type,
                action=f"子任务 {task_id} {'完成' if sub_task.status == TaskStatus.COMPLETED else '失败'}",
                detail={"description": sub_task.description, "result_preview": (sub_task.result or "")[:300]},
            ))

        return steps

    @staticmethod
    async def _run_sub_task(sub_task: SubTask, context: str) -> str:
        """运行单个子任务。"""
        agent = AgentFactory.create(sub_task.agent_type)
        sub_task.status = TaskStatus.IN_PROGRESS
        logger.info(f"  [{sub_task.agent_type}] 开始: {sub_task.description}")
        return await agent.run(sub_task.description, context=context)

    @staticmethod
    def _build_dependency_context(sub_task: SubTask, task_results: dict[str, str]) -> str:
        """将前置任务的结果组装为上下文。"""
        if not sub_task.dependencies:
            return ""
        parts = [
            f"[{dep_id} 的结果]:\n{task_results[dep_id]}"
            for dep_id in sub_task.dependencies
            if dep_id in task_results
        ]
        return "\n\n".join(parts)

    @staticmethod
    async def _aggregate_results(
        user_input: str,
        plan: TaskPlan,
        task_results: dict[str, str],
    ) -> str:
        """汇总所有子任务结果，生成最终响应。"""
        parts: list[str] = []
        for task in plan.sub_tasks:
            status_str = "完成" if task.status == TaskStatus.COMPLETED else "失败"
            parts.append(
                f"### 子任务: {task.description}\n"
                f"类型: {task.agent_type} | 状态: {status_str}\n"
                f"结果:\n{task_results.get(task.id, '无结果')}"
            )

        messages = [
            {"role": "system", "content": RESULT_AGGREGATE_PROMPT},
            {"role": "user", "content": (
                f"用户原始请求: {user_input}\n\n"
                f"各子任务执行结果:\n\n" + "\n\n---\n\n".join(parts)
            )},
        ]
        response = await llm_client.chat_completion(messages)
        return response.get("content", "结果汇总失败")
