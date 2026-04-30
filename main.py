"""FastAPI 入口，提供多 Agent 协同工作流的 HTTP 接口。"""
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from config import LOG_LEVEL
from llm_client import llm_client
from models import ChatRequest, ChatResponse
from workflow import WorkflowPipeline

# --- 日志配置 ---
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format=(
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{message}</cyan>"
))
logger.add(
    "logs/workflow_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)

pipeline = WorkflowPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("多Agent协同工作流服务已启动")
    yield
    await llm_client.close()
    logger.info("服务已关闭")


app = FastAPI(
    title="多Agent协同工作流",
    description="模拟 Cursor 风格的多 Agent 协同工作流程",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """主聊天接口 — 触发完整的多 Agent 工作流。

    接收用户消息，依次经过:
    1. 上下文组装 + 意图解析
    2. 任务规划与调度
    3. 工具路由 + 任务执行（多Agent并行）
    4. 结果汇总
    """
    request_id = str(uuid.uuid4())
    logger.info(f"收到请求 [{request_id}]: {request.message[:100]}")

    try:
        response = await pipeline.run(request)
        return response
    except Exception as e:
        logger.exception(f"工作流执行失败 [{request_id}]")
        return ChatResponse(
            code=500,
            message=f"工作流执行失败: {e}",
            request_id=request_id,
            data={},
        )


@app.get("/health")
async def health():
    """健康检查接口。"""
    return {"status": "ok", "service": "multi-agent-workflow"}
