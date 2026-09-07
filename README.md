# 制造业智能化 AI Agent Demo

基于 MCP（Model Context Protocol）协议的制造业 AI Agent 演示项目，展示如何用大模型驱动企业内部系统的智能问答与操作编排。

## 项目特性

- **MCP 协议对接**：通过 MCP Server 将设备管理、生产调度、质量检测、知识库等企业系统封装为标准化工具
- **LangGraph 智能编排**：基于状态机的多轮推理工作流，支持工具调用、RAG 检索、结果聚合
- **制造业场景模拟**：内置离散制造车间模拟器，生成设备状态、工单、质检、库存等真实感数据
- **流式对话接口**：FastAPI + SSE 流式输出，支持逐 token 渲染与中间思考过程展示
- **可视化前端**：聊天面板 + 实时数据看板 + 设备拓扑图，一体化交互体验

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 引擎 | LangChain + LangGraph |
| 工具协议 | MCP (Model Context Protocol) |
| 向量检索 | ChromaDB + sentence-transformers |
| API 层 | FastAPI + Uvicorn |
| 数据模拟 | Pandas + NumPy |
| 前端 | Vue 3 + Vite + ECharts |
| 测试 | Pytest + pytest-asyncio |

## 目录结构

```
manufacturing-ai-agent-demo/
├── backend/
│   ├── agent/              # AI Agent 核心（LangGraph 工作流、工具注册、RAG）
│   ├── api/                # FastAPI 路由与接口
│   ├── data/               # 模拟数据（生成后忽略）
│   ├── mcp_servers/        # MCP 服务器集群
│   └── simulator/          # 制造业场景模拟器
├── frontend/               # 前端界面
├── docs/                   # 项目文档
├── tests/                  # 测试用例
├── blog/                   # 技术博客文章
├── pyproject.toml          # Python 项目配置
└── README.md
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等配置
```

### 3. 生成模拟数据

```bash
python -m backend.simulator.generate_all
```

### 4. 启动后端服务

```bash
uvicorn backend.api.main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

## 核心场景演示

### 场景一：设备异常诊断

> 用户："3 号 CNC 机床今天报警了吗？什么原因？"

Agent 调用设备管理 MCP Server 查询报警记录 → 结合知识库 RAG 检索故障手册 → 给出诊断结论与处理建议。

### 场景二：生产排程查询

> 用户："本周 A 线的工单完成率怎么样？哪个工单延期了？"

Agent 调用生产调度 MCP Server 查询工单状态 → 聚合统计 → 识别延期工单及原因。

### 场景三：质量追溯

> 用户："批次 LOT-20260901-003 的不良品主要是什么缺陷？关联到哪台设备？"

Agent 调用质量检测 MCP Server 查询质检记录 → 按缺陷类型聚合 → 关联设备与工艺参数。

## MCP 服务器清单

| 服务器 | 功能 | 核心工具 |
|--------|------|----------|
| `equipment_mcp` | 设备管理 | 查询设备状态、报警记录、维护计划 |
| `production_mcp` | 生产调度 | 查询工单、排程、产能统计 |
| `quality_mcp` | 质量检测 | 查询质检记录、缺陷分析、批次追溯 |
| `knowledge_mcp` | 知识库 | 故障手册检索、工艺文档查询 |

## 许可证

MIT License
