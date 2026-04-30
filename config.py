"""应用配置模块，统一管理所有可配置项。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Agent 配置
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

# 工作空间配置
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", str(Path(__file__).parent / "workspace")))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 阿里云 MCP 服务配置（联网搜索、网页解析）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", LLM_API_KEY)
WEBSEARCH_MCP_URL = os.getenv(
    "WEBSEARCH_MCP_URL",
    "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp",
)
WEBPARSER_MCP_URL = os.getenv(
    "WEBPARSER_MCP_URL",
    "https://dashscope.aliyuncs.com/api/v1/mcps/WebParser/sse",
)
