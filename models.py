"""数据模型定义，涵盖工作流各阶段所需的结构体。"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    """Agent 工作模式。"""
    AGENT = "agent"
    PLAN = "plan"
    EXPLORE = "explore"


class SubAgentType(str, Enum):
    """子 Agent 类型。"""
    EXPLORE = "explore"
    CODE = "code"
    SHELL = "shell"
    GENERAL = "general"


class TaskStatus(str, Enum):
    """任务状态。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------- 工具相关 ----------

class ToolCallResult(BaseModel):
    """工具调用结果。"""
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None


# ---------- 任务相关 ----------

class SubTask(BaseModel):
    """子任务定义。"""
    id: str
    description: str
    agent_type: str
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None


class TaskPlan(BaseModel):
    """任务计划，包含多个子任务。"""
    mode: AgentMode
    reasoning: str
    sub_tasks: list[SubTask] = Field(default_factory=list)


# ---------- 上下文 ----------

class WorkflowContext(BaseModel):
    """工作流上下文，贯穿整个管线。"""
    user_input: str
    workspace_path: str = ""
    file_contents: dict[str, str] = Field(default_factory=dict)
    directory_tree: str = ""


# ---------- 执行记录 ----------

class AgentStep(BaseModel):
    """Agent 执行步骤记录，用于结果追溯。"""
    stage: str
    agent_type: str = ""
    action: str
    detail: Any = None


# ---------- API 模型 ----------

class ChatRequest(BaseModel):
    """聊天请求。"""
    message: str
    workspace_path: str | None = None
    include_files: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """聊天响应，遵循项目统一响应格式。"""
    code: int = 200
    message: str = "success"
    request_id: str
    data: dict[str, Any] = Field(default_factory=dict)
