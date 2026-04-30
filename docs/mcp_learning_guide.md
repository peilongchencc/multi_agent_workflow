# MCP（Model Context Protocol）学习指南

> 本文档整理自 Cursor 对话，帮助你从零理解 MCP 的概念、与传统工具调用的区别、以及如何在 Cursor 中实际使用 MCP。

---

## 目录

1. [Cursor Agents Window 简介](#1-cursor-agents-window-简介)
2. [传统大模型工具调用（Function Calling）](#2-传统大模型工具调用function-calling)
3. [MCP 是什么](#3-mcp-是什么)
4. [MCP vs 传统工具调用的区别](#4-mcp-vs-传统工具调用的区别)
5. [个人开发者能写 MCP 吗](#5-个人开发者能写-mcp-吗)
6. [MCP 需要付费吗](#6-mcp-需要付费吗)
7. [去哪里找好用的 MCP Server](#7-去哪里找好用的-mcp-server)
8. [实战：在 Cursor 中配置 MCP Server](#8-实战在-cursor-中配置-mcp-server)
9. [MCP 使用示例](#9-mcp-使用示例)
10. [常见问题](#10-常见问题)

---

## 1. Cursor Agents Window 简介

Cursor 3（2026年4月发布）引入了 **Agents Window**，这是一个以 Agent 为中心的全新界面。

### 与编辑器内 Agent 的区别

| 特性 | 编辑器内 Agent（Editor Window） | Agents Window |
|---|---|---|
| **定位** | 传统 IDE 体验 + AI 辅助 | 以 Agent 为核心的全新界面 |
| **并行能力** | 单个聊天中顺序执行任务 | 可并行运行多个 Agent（含云端 Agent） |
| **工作区** | 一次打开一个项目 | 一个界面管理多个项目 |
| **文件编辑** | 完整 VS Code 编辑器，多文件并排查看 | 轻量化文件查看，专注于 Agent 交互 |
| **VS Code 扩展** | 完整支持 | 受限 |
| **云端 Agent** | 可以启动，但管理不方便 | 原生集成，轻松启动、监控和管理 |
| **PR/Diff 管理** | 需要外部工具 | 内置 Diffs 视图 |

### Marketplace

Agents Window 中的 **Marketplace** 是 Cursor 的官方插件市场，可以一键安装：

- **Rules** - 持久化的 AI 指导规则和编码标准
- **Skills** - 专门的 Agent 能力
- **MCP Servers** - 外部工具集成（如 Datadog、Slack、Figma 等）
- **Hooks** - 事件触发的自动化脚本

所有官方 Marketplace 插件都经过人工安全审查。

---

## 2. 传统大模型工具调用（Function Calling）

传统的大模型工具调用流程如下：

```
用户提问 → 大模型判断需要调用工具 → 输出函数名+参数(JSON)
→ 你的代码执行函数 → 结果返回给大模型 → 大模型生成最终回答
```

### 示例代码

```python
# 1. 自己写一个函数
def get_weather(city: str) -> str:
    """查询城市天气。"""
    # 调用天气API ...

# 2. 用 JSON Schema 告诉大模型"你有这个工具可以用"
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询城市天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"}
            }
        }
    }
}]

# 3. 大模型返回: {"name": "get_weather", "arguments": {"city": "北京"}}
# 4. 你的代码解析并执行这个函数，把结果喂回给大模型
```

### 痛点

- 每个项目都要自己写一套集成代码
- 工具和应用是**紧耦合**的
- 换个项目/应用，工具要重写一遍

---

## 3. MCP 是什么

**MCP（Model Context Protocol）** 是 Anthropic 在 2024 年底开源的一个**标准化协议**，目的是统一"AI 应用如何连接外部工具和数据"。

### 类比：USB-C 接口

- 以前每个手机品牌用不同的充电口（Micro USB、Lightning），每换一个设备就得换一根线
- USB-C 出来后，一根线通吃所有设备

MCP 做的事情类似：

```
传统方式：每个 AI 应用 × 每个工具 = N×M 个自定义集成
MCP 方式：每个工具做一个 MCP Server，每个 AI 应用做一个 MCP Client = N+M 个标准实现
```

### 架构图

```
传统方式（紧耦合）：
┌─────────────┐
│   你的应用   │
│  ├─ 天气函数（自己写的）
│  ├─ 数据库查询函数（自己写的）
│  └─ 发邮件函数（自己写的）
└─────────────┘

MCP 方式（标准化、解耦）：
┌──────────────┐                  ┌──────────────────┐
│  MCP Client  │ ◄──(JSON-RPC)──► │  MCP Server: 天气  │
│  (Cursor、   │ ◄──(JSON-RPC)──► │  MCP Server: 数据库 │
│   Claude等)  │ ◄──(JSON-RPC)──► │  MCP Server: Slack │
└──────────────┘                  └──────────────────┘
```

### MCP 的即插即用特性

传统方式，即使有人把天气函数做成了 API，你仍然需要：

```python
# 手动写 schema、调用逻辑、分发逻辑……
tools = [{"type": "function", "function": {"name": "get_weather", ...}}]

def get_weather(city):
    resp = requests.get(f"https://weather-api.com/?city={city}")
    return resp.json()

if tool_call.name == "get_weather":
    result = get_weather(**tool_call.arguments)
```

MCP 方式，你只需要写几行配置：

```json
{
  "mcpServers": {
    "weather": {
      "command": "npx",
      "args": ["mcp-server-weather"]
    }
  }
}
```

然后 Cursor（MCP Client）会**自动**：

1. 问 Server："你有哪些工具？"
2. Server 回答："我有 `get_weather`、`get_forecast` 等"
3. 把这些工具自动注册给大模型
4. 大模型调用时，自动把参数转发给 Server，把结果拿回来

**你不需要写任何函数、任何 schema、任何分发逻辑。**

---

## 4. MCP vs 传统工具调用的区别

| | 传统 Function Calling | MCP |
|---|---|---|
| **本质** | 大模型的一种能力（输出结构化的函数调用） | 一个**开放协议/标准**（规定了通信格式） |
| **谁写工具** | 你自己在应用代码里写 | 任何人可以写 MCP Server，社区共享 |
| **可复用性** | 工具和应用绑定，换个应用得重写 | 一个 MCP Server 可被所有 MCP Client 使用 |
| **发现机制** | 你手动在代码里注册工具列表 | Client 自动向 Server 查询可用工具 |
| **提供内容** | 只有 Tools（函数） | Tools + Resources（数据）+ Prompts（提示词模板） |
| **运行方式** | 函数在你的应用进程内执行 | MCP Server 是独立进程，通过 stdio 或 HTTP(SSE) 通信 |

### 它们是互斥的吗？

**不是。** MCP 底层仍然依赖大模型的 Function Calling 能力。

- **Function Calling** 是大模型的"手"——它能输出"我想调用某个函数"的指令
- **MCP** 是"手"和"工具"之间的**标准接口**——规定了工具怎么暴露、怎么被发现、怎么通信

### 更准确的类比

> **传统工具调用** = 你买了一台打印机，需要自己去网上找驱动、下载、安装、配置端口，每换一台打印机就重来一遍。
>
> **MCP** = USB 即插即用标准。你把打印机插上 USB，操作系统自动识别、自动装驱动、自动可用。你只需要"插上去"（写几行配置），剩下的系统全搞定。

---

## 5. 个人开发者能写 MCP 吗

**当然可以！** MCP 是完全开源的协议，任何人都可以写 MCP Server。

### 谁在写 MCP Server？

| 来源 | 示例 |
|---|---|
| **Anthropic 官方** | filesystem、fetch、memory、github、slack 等 |
| **各大公司** | Datadog、Figma、Linear、Sentry 等 |
| **个人开发者** | 大量社区贡献的 MCP Server |

### 个人开发者写 MCP 的场景

- 你公司有内部 API，想让 AI 能调用 → 自己写一个 MCP Server 包装一下
- 你有一个自定义的数据库/服务 → 写 MCP Server 让 Cursor 直接查询
- 你想把自己常用的工具标准化 → 写成 MCP Server，所有支持 MCP 的 AI 应用都能用

### 如何写？

MCP 官方提供了多种语言的 SDK：

- **Python**: `pip install mcp`
- **TypeScript**: `npm install @modelcontextprotocol/sdk`
- **其他语言**: 社区也有 Go、Rust、Java 等实现

官方文档：https://modelcontextprotocol.io

---

## 6. MCP 需要付费吗

### MCP 协议本身

**完全免费开源。** 协议、SDK、官方 Server 都是开源的。

### MCP Server 是否免费

取决于具体的 Server：

| 类型 | 是否免费 | 示例 |
|---|---|---|
| **官方基础 Server** | 完全免费 | filesystem、fetch、memory |
| **需要第三方账号的 Server** | Server 本身免费，但第三方服务可能收费 | Datadog（需要 Datadog 账号）、Slack（需要 Slack workspace） |
| **纯本地 Server** | 完全免费 | filesystem、memory |

本项目配置的 3 个本地 MCP Server 全部免费，无需任何 API Key。

阿里云百炼 MCP 广场的服务（联网搜索、网页解析等）限时免费，每月 2000 次免费额度，需要百炼 API Key。

---

## 7. 去哪里找好用的 MCP Server

### 主流 MCP 发现平台

| 平台 | 地址 | 特点 |
|---|---|---|
| **MCP 官方 Server 仓库** | https://github.com/modelcontextprotocol/servers | Anthropic 官方维护，最权威 |
| **Cursor Marketplace** | Cursor Agents Window 内置 | 经过人工安全审查，一键安装 |
| **PulseMCP** | https://pulsemcp.com | 最大的活跃维护目录，11,000+ Server |
| **MCP.so** | https://mcp.so | 社区驱动，19,400+ Server |
| **Smithery** | https://smithery.ai | 市场风格，支持 CLI 管理和托管 |
| **Glama** | https://glama.ai/mcp/servers | 策划型目录，自动+手动安全扫描 |
| **MCP Scoreboard** | https://mcpscoreboard.com | 30,000+ Server 的独立质量评分 |
| **MCP Find** | https://mcpfind.org | 开源目录，6,700+ 已验证 Server |
| **cursor.directory** | https://cursor.directory | 社区贡献的 Cursor 专用 MCP 和 Rules |

### 国内平台

| 平台 | 地址 | 特点 |
|---|---|---|
| **阿里云百炼 MCP 广场** | https://bailian.console.aliyun.com (MCP广场) | 联网搜索、网页解析、代码解释器等，限时免费 |

### 建议

- **入门**：从 Cursor Marketplace 或官方 Server 仓库开始
- **找特定功能**：去 PulseMCP 或 MCP.so 搜索
- **评估质量**：用 MCP Scoreboard 查看评分
- **国内服务**：阿里云百炼 MCP 广场

---

## 8. 实战：在 Cursor 中配置 MCP Server

### 配置文件位置

- **项目级**：`.cursor/mcp.json`（仅对当前项目生效）
- **全局**：`~/.cursor/mcp.json`（对所有项目生效）

### 本项目的配置

文件路径：`.cursor/mcp.json`

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/peilongchencc/Desktop/multi_agent_workflow"
      ]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "fetch": {
      "command": "/Users/peilongchencc/miniforge3/bin/python",
      "args": ["-m", "mcp_server_fetch"]
    },
    "aliyun-web-search": {
      "type": "streamable-http",
      "url": "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp",
      "headers": {
        "Authorization": "Bearer 你的百炼API_KEY"
      }
    },
    "aliyun-read-page": {
      "type": "streamable-http",
      "url": "https://iqs-mcp.aliyuncs.com/mcp-servers/iqs-mcp-server-readpage",
      "headers": {
        "X-API-Key": "你的百炼API_KEY"
      }
    }
  }
}
```

### MCP Server 类型说明

本项目配置了两种类型的 MCP Server：

**本地 Server（command 类型）**：在你电脑上运行的进程，通过 stdio 通信，无需网络。

**远程 Server（streamable-http 类型）**：运行在云端的服务，通过 HTTP 通信，需要 API Key 认证。

### 五个 MCP Server 说明

#### 1. Filesystem（文件系统）- 本地

- **来源**：Anthropic 官方
- **安装方式**：`npx`（自动安装，无需手动操作）
- **费用**：免费
- **功能**：让 AI 能够安全地读写项目目录中的文件
- **可用工具**：
  - `read_file` - 读取文件内容
  - `write_file` - 写入文件
  - `list_directory` - 列出目录内容
  - `create_directory` - 创建目录
  - `move_file` - 移动/重命名文件
  - `search_files` - 搜索文件
  - `get_file_info` - 获取文件信息

#### 2. Memory（记忆/知识图谱）- 本地

- **来源**：Anthropic 官方
- **安装方式**：`npx`（自动安装）
- **费用**：免费
- **功能**：基于知识图谱的持久化记忆系统，让 AI 能在对话之间保留和检索信息
- **可用工具**：
  - `create_entities` - 创建实体（如：人、项目、概念）
  - `create_relations` - 创建实体间的关系
  - `search_nodes` - 搜索知识图谱
  - `open_nodes` - 查看特定实体的详细信息
  - `delete_entities` / `delete_relations` - 删除实体或关系

#### 3. Fetch（网页抓取）- 本地

- **来源**：Anthropic 官方
- **安装方式**：`pip install mcp-server-fetch`（已安装）
- **费用**：免费
- **功能**：抓取网页内容并转换为 Markdown 等格式
- **可用工具**：
  - `fetch` - 抓取 URL 内容（支持 HTML → Markdown 转换）

#### 4. 阿里云联网搜索（WebSearch）- 远程

- **来源**：阿里云百炼 MCP 广场
- **费用**：限时免费，每月 2000 次免费额度
- **认证**：需要百炼通用 API Key（格式：`sk-xxx`）
- **功能**：实时联网搜索，获取最新的网络信息
- **端点**：`https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp`
- **协议**：Streamable HTTP（新版协议）

#### 5. 阿里云网页解析（ReadPage）- 远程

- **来源**：阿里云信息查询服务（IQS）
- **费用**：限时免费，每月 2000 次免费额度
- **认证**：需要百炼 API Key
- **功能**：解析网页内容，支持静态和动态渲染两种模式
- **端点**：`https://iqs-mcp.aliyuncs.com/mcp-servers/iqs-mcp-server-readpage`
- **可用工具**：
  - `readpage_basic` - 静态网页解析
  - `readpage_scrape` - 动态渲染解析（通过无头浏览器）

### 配置后如何生效

1. 保存 `.cursor/mcp.json` 文件
2. **完全退出 Cursor 并重新打开**（重要！）
3. 在 Cursor 聊天中，AI 会自动发现并可以使用这些 MCP 工具

### 验证是否生效

在 Cursor Settings → MCP 中可以看到已配置的 Server 及其状态（绿色表示正常运行）。

---

## 9. MCP 使用示例

配置好 MCP 后，你可以在 Cursor 中这样使用：

### Filesystem 示例

> 你："帮我列出 workspace 目录下的所有文件"

AI 会自动调用 `filesystem` MCP Server 的 `list_directory` 工具。

### Memory 示例

> 你："记住：这个项目使用 FastAPI 框架，数据库用的是 PostgreSQL"

AI 会调用 `memory` MCP Server 的 `create_entities` 和 `create_relations` 工具，将这些信息存入知识图谱。

> 你（下次对话）："这个项目用什么框架来着？"

AI 会调用 `search_nodes` 从记忆中检索。

### Fetch 示例

> 你："帮我抓取 https://docs.python.org/3/whatsnew/3.12.html 的内容"

AI 会调用 `fetch` MCP Server 获取网页内容并转换为可读格式。

### 阿里云联网搜索示例

> 你："用 aliyun-web-search 搜索 Python 3.13 有哪些新特性"

AI 会调用阿里云联网搜索 MCP 获取实时搜索结果。

### 阿里云网页解析示例

> 你："用 aliyun-read-page 解析 https://fastapi.tiangolo.com 的内容"

AI 会调用阿里云网页解析 MCP 提取网页内容。

---

## 10. 常见问题

### Q: MCP Server 运行在哪里？

大部分 MCP Server 运行在你的**本机**，作为一个独立进程。Cursor 通过 `stdio`（标准输入/输出）和它通信。也有部分 Server 通过 HTTP+SSE 运行在远程。

### Q: MCP Server 会消耗很多资源吗？

不会。大部分 MCP Server 是轻量级进程，只在被调用时才会活跃。

### Q: 我的 API Key 安全吗？

MCP 配置中的 API Key 存储在本地的 `mcp.json` 文件中。建议：

- 将 `.cursor/mcp.json` 加入 `.gitignore`（如果包含密钥）
- 或使用环境变量引用密钥

### Q: 如何查看有哪些 MCP Server 可用？

- 官方仓库：https://github.com/modelcontextprotocol/servers
- Cursor Marketplace（Agents Window 中）
- PulseMCP：https://pulsemcp.com（最大的活跃维护目录）
- MCP.so：https://mcp.so（社区驱动，数量最多）
- 阿里云百炼 MCP 广场（国内平台）
- 社区目录：https://cursor.directory

### Q: 一句话总结 MCP

传统工具调用是"大模型会调函数"，MCP 是"让所有 AI 应用和所有工具之间有一个统一的对话标准"。MCP 不是替代 Function Calling，而是在它之上建立了一层**标准化的生态协议**。

---

## 参考链接

- MCP 官方文档：https://modelcontextprotocol.io
- MCP 官方 Server 仓库：https://github.com/modelcontextprotocol/servers
- Cursor MCP 文档：https://docs.cursor.com/context/model-context-protocol
- Cursor Marketplace：https://cursor.com/marketplace
- 阿里云百炼 MCP 广场：https://bailian.console.aliyun.com (MCP广场)
- 阿里云联网搜索 MCP 文档：https://help.aliyun.com/zh/model-studio/web-search-for-coding-plan
- PulseMCP（MCP Server 目录）：https://pulsemcp.com
- MCP.so（社区 MCP 目录）：https://mcp.so
