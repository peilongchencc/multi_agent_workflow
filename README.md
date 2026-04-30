# 多 Agent 协同工作流 (Multi-Agent Workflow)

模拟 Cursor 风格的多 Agent 协同工作流程。通过将用户请求经过 **意图解析 → 任务规划 → 并行执行 → 结果汇总** 的完整管线，展示 Agent 系统的核心工作机制。

## 工作流架构

```
用户输入
   │
   ▼
┌──────────────────────────────────────┐
│ Stage 1: 上下文组装 + 意图解析 + 模式路由  │
│  - ContextBuilder: 收集工作空间信息       │
│  - IntentParser: LLM判断模式和所需Agent   │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Stage 2: 任务规划与调度                  │
│  - TaskScheduler: LLM拆解子任务         │
│  - 依赖解析: 生成分层并行执行计划          │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Stage 3-4: 工具路由 + 任务执行           │
│  ┌─────────────────────────────┐     │
│  │ 执行→观察→修正 循环 (ReAct)   │     │
│  │  - LLM选择工具 + 推理参数     │     │
│  │  - 执行工具，观察结果         │     │
│  │  - 判断是否继续/修正/完成     │     │
│  └─────────────────────────────┘     │
│  * 同层任务并行，跨层任务串行            │
│  * explore/code/shell 子Agent协同     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Stage 5: 结果汇总 + 响应生成             │
│  - LLM汇总所有子任务结果               │
│  - 生成最终用户可读的报告               │
└──────────────────────────────────────┘
```

## 项目结构

```
multi_agent_workflow/
├── main.py                 # FastAPI 入口
├── config.py               # 配置管理
├── models.py               # 数据模型
├── prompts.py              # LLM 提示词
├── llm_client.py           # 异步 LLM 客户端 (aiohttp)
├── workflow.py             # 主工作流管线
├── core/
│   ├── context_builder.py  # Stage 1: 上下文构建
│   ├── intent_parser.py    # Stage 1: 意图解析
│   └── task_scheduler.py   # Stage 2: 任务调度
├── agents/
│   ├── base.py             # Agent 基类 (ReAct 循环)
│   ├── factory.py          # Agent 工厂
│   ├── explore_agent.py    # 探索型 Agent (只读)
│   ├── code_agent.py       # 代码型 Agent (读写)
│   └── shell_agent.py      # Shell 型 Agent (命令执行)
├── tools/
│   ├── registry.py         # 工具注册表
│   ├── file_tools.py       # 文件操作工具
│   └── shell_tools.py      # Shell 命令工具
├── docs/
│   └── mcp_learning_guide.md  # MCP 学习指南
├── .cursor/
│   └── mcp.json            # MCP Server 配置
└── workspace/
    └── sample_data.csv     # 示例数据
```

## 快速开始

### 1. 创建 Conda 环境

```bash
conda create -n agentsflow python=3.11 -y
conda activate agentsflow
```

### 2. 安装依赖

```bash
cd multi_agent_workflow
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key。当前项目使用阿里云百炼（DashScope）：

```env
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-plus
```

> 支持所有兼容 OpenAI API 格式的服务商（OpenAI、DeepSeek、通义千问等），只需修改 `LLM_BASE_URL` 和 `LLM_MODEL`。

### 4. 启动服务

```bash
conda activate agentsflow
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. 发送请求

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我分析 workspace 中的 sample_data.csv，生成一个统计报告脚本"}'
```

访问 `http://localhost:8000/docs` 可查看 Swagger 交互式文档。

## API 说明

### POST /chat

发送用户消息，触发完整的多 Agent 工作流。

**请求体:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户输入的消息 |
| workspace_path | string | 否 | 自定义工作空间路径 |
| include_files | string[] | 否 | 需要预加载的文件路径列表 |

**响应体:**

```json
{
  "code": 200,
  "message": "success",
  "request_id": "uuid",
  "data": {
    "response": "最终汇总结果...",
    "workflow_steps": [...],
    "task_plan": {...}
  }
}
```

- `response`: 最终面向用户的汇总结果
- `workflow_steps`: 完整的工作流执行步骤记录（可用于调试和分析）
- `task_plan`: 任务规划详情（包含子任务列表、依赖关系、执行状态）

### GET /health

健康检查接口。

## 示例场景

**场景 1: 数据分析**
```json
{"message": "分析 sample_data.csv 的数据，告诉我各部门的平均薪资和人数"}
```
工作流: explore(读取CSV) → code(写分析脚本) → shell(运行脚本)

**场景 2: 代码生成**
```json
{"message": "帮我写一个 Python 的快速排序算法，保存为 quicksort.py"}
```
工作流: code(编写代码)

**场景 3: 项目探索**
```json
{"message": "帮我看看 workspace 里有什么文件，分析一下项目结构"}
```
工作流: explore(遍历目录和文件)

## 配置说明

所有配置通过 `.env` 文件或环境变量设置:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| LLM_API_KEY | (必填) | LLM API 密钥 |
| LLM_BASE_URL | https://dashscope.aliyuncs.com/compatible-mode/v1 | API 基础 URL |
| LLM_MODEL | qwen3.6-plus | 使用的模型 |
| LLM_MAX_TOKENS | 4096 | 最大生成 token 数 |
| LLM_TEMPERATURE | 0.7 | 温度参数 |
| MAX_AGENT_ITERATIONS | 10 | 单个Agent最大迭代次数 |
| WORKSPACE_DIR | ./workspace | 工作空间目录 |
| LOG_LEVEL | INFO | 日志级别 |

## MCP 配置

项目集成了 5 个 MCP Server（配置文件：`.cursor/mcp.json`），用于增强 Cursor IDE 中的 AI 能力。

### 本地 MCP Server（免费，无需 API Key）

| 名称 | 功能 | 安装方式 |
|------|------|----------|
| filesystem | 文件读写、目录浏览、文件搜索 | npx（自动） |
| memory | 基于知识图谱的持久化记忆 | npx（自动） |
| fetch | 抓取网页内容并转为 Markdown | pip install mcp-server-fetch |

### 远程 MCP Server（阿里云百炼，限时免费，每月 2000 次）

| 名称 | 功能 | 端点 |
|------|------|------|
| aliyun-web-search | 实时联网搜索 | dashscope.aliyuncs.com |
| aliyun-read-page | 网页解析（静态+动态渲染） | iqs-mcp.aliyuncs.com |

> 远程 MCP Server 需要百炼通用 API Key（`sk-xxx` 格式），配置在 `.cursor/mcp.json` 中。

### MCP 配置生效方式

1. 编辑 `.cursor/mcp.json`，填入 API Key
2. 完全退出 Cursor 并重新打开
3. 在 Cursor Settings → MCP 中确认状态为绿色

详细的 MCP 学习资料请参考 [MCP 学习指南](docs/mcp_learning_guide.md)。
