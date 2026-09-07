# 制造业智能化 AI Agent Demo

一个可本地运行的制造业 Agent 演示项目，覆盖设备监控、MES 工单、质量与库存查询、SOP 检索，以及只生成草稿的工单操作。

## 能展示什么

- 设备状态、告警和温度看板
- 工单列表、工单详情和生产统计
- 物料齐套、库存预警和质量分析
- SOP 与故障代码查询
- Agent 工具调用过程和 SSE 流式回复
- 工单草稿生成，默认不会写入真实系统

项目自带确定性的模拟数据，不配置大模型 Key 也可以完整演示。配置 OpenAI 兼容接口后，可以切换到 LLM 工具调用模式。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Agent 编排 | LangGraph + LangChain Core |
| API | FastAPI + Uvicorn |
| 工具层 | FastMCP 兼容适配层 |
| 检索 | 本地关键词兜底；可选 ChromaDB + FastEmbed |
| 数据 | JSON 模拟数据 + NumPy/Pandas |
| 前端 | React 18 + TypeScript + Vite + ECharts |

## 快速启动

需要 Python 3.11+、Node.js 18+。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd frontend
npm install
cd ..

./scripts/start_demo.sh
```

启动后访问 <http://localhost:5173>。

脚本会自动生成模拟数据并启动：

- 前端：<http://localhost:5173>
- 后端：<http://localhost:8000>
- 健康检查：<http://localhost:8000/api/health>

## 推荐演示问题

```text
现在有哪些设备告警？
CNC-001状态怎么样？
本周生产情况怎么样？
WO-2026-0001的物料齐套吗？
E001是什么故障？
怎么换模？
帮我创建一个工单
```

## 可选能力

### LLM 模式

```bash
pip install -e ".[dev,llm]"
export OPENAI_API_KEY="your-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"
./scripts/start_demo.sh
```

没有 `OPENAI_API_KEY` 时，系统自动使用规则 Mock 模式，适合离线演示。

### 向量检索

默认使用本地关键词检索，启动快且不需要下载模型。需要启用 ChromaDB + FastEmbed 时：

```bash
pip install -e ".[dev,rag]"
export ENABLE_VECTOR_RAG=1
./scripts/start_demo.sh
```

## 项目结构

```text
backend/
  agent/              Agent 状态机、工具注册和回复生成
  mcp_servers/        设备、MES、知识库工具
  simulator/          确定性模拟数据生成器
  main.py             FastAPI 入口
frontend/             React 前端和设备看板
scripts/              本地启动脚本
tests/                冒烟测试
docs/                 技术报告和评测记录
```

## 测试

```bash
.venv/bin/pytest -q
cd frontend && npm run build
```

MCP 服务器模块保留了 FastMCP 入口；Agent 的本地演示调用通过兼容层工作，从而避免 MCP SDK 版本变化阻塞基础 Demo。生产接入时，应将这些工具替换为经过权限控制的 MES、ERP、WMS 或设备 API。

## 许可证

MIT License
