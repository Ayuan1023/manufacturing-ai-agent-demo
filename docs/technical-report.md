# 制造业内部系统智能化 AI Agent 技术报告

**版本**：v1.0  
**日期**：2026-09-07  
**项目**：manufacturing-ai-agent-demo  
**仓库**：https://github.com/Ayuan1023/manufacturing-ai-agent-demo

---

## 一、项目概述

### 1.1 背景

制造业企业内部存在大量异构系统（MES、ERP、SCADA、设备管理、知识库等），数据分散在不同系统中，一线工程师和管理人员需要在多个系统间切换查询信息，效率低下。本项目旨在构建一个基于大语言模型的智能运维 Agent，通过自然语言统一查询设备状态、生产工单、物料库存、操作规程等信息，实现"问一句，答全部"的智能交互体验。

### 1.2 目标

- **统一入口**：通过自然语言对话查询制造业内部多系统数据
- **可解释性**：展示 Agent 调用了哪些工具、获取了什么数据，推理过程透明
- **流式体验**：SSE 逐字输出，工具调用实时展示，降低等待焦虑
- **安全可控**：OT 层默认只读，写操作需人工确认（HITL）
- **可扩展**：MCP 标准化工具接口，新增系统只需添加 MCP Server

### 1.3 Demo 场景

| 场景 | 示例查询 | 调用工具 |
|------|---------|---------|
| 设备查询 | "现在有哪些设备告警？" | get_alarm_equipment + get_equipment_list |
| SOP 检索 | "怎么换模？" | search_sop（RAG 语义搜索） |
| 异常诊断 | "E001 是什么故障？" | search_fault_code + get_alarm_equipment |
| 预测维护 | "CNC-001 最近维护记录" | get_equipment_history + get_maintenance_history |
| 工单分析 | "本周生产情况怎么样？" | get_production_stats |
| 物料齐套 | "WO-2026-0001 的物料齐套吗？" | get_work_order_detail + check_material_availability |
| 工单草稿 | "帮我创建一个工单" | create_work_order_draft（HITL 待确认） |

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端展示层                              │
│  Vite + React + TypeScript + shadcn/ui + Tailwind + ECharts │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │  聊天面板     │  │  设备监控面板                         │ │
│  │  SSE流式输出  │  │  ECharts温度图 + 状态统计 + 设备列表  │ │
│  │  工具调用卡片  │  │  30秒自动轮询                        │ │
│  └──────┬───────┘  └──────────────────────────────────────┘ │
└─────────┼───────────────────────────────────────────────────┘
          │ HTTP/SSE
┌─────────▼───────────────────────────────────────────────────┐
│                    API 网关层 (FastAPI)                       │
│  /api/chat/stream (SSE)  /api/chat  /api/equipment/status    │
│  /api/sessions/{id}  /api/tools  /api/health                 │
│  会话管理 | CORS | 全局错误处理 | SSE保活                     │
└─────────┬───────────────────────────────────────────────────┘
          │ 函数调用
┌─────────▼───────────────────────────────────────────────────┐
│                  Agent 编排层 (LangGraph)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  StateGraph: __start__ → agent → tools → agent → END   │ │
│  │  双模式运行: LLM模式 | Mock模式(规则引擎降级)            │ │
│  │  HITL: pending_confirmation 写操作中断等待确认           │ │
│  │  recursion_limit=15 防死循环                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────┬───────────────────────────────────────────────────┘
          │ StructuredTool 调用
┌─────────▼───────────────────────────────────────────────────┐
│                    MCP 工具层 (FastMCP)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │ 设备MCP     │  │ MES MCP    │  │ 知识MCP (RAG)          │ │
│  │ 6个工具     │  │ 7个工具    │  │ 5个工具                │ │
│  │ 设备列表/   │  │ 工单查询/  │  │ SOP语义搜索/           │ │
│  │ 状态/告警/  │  │ 详情/统计/ │  │ 详情/列表/             │ │
│  │ 历史/异常/  │  │ 质量/齐套/ │  │ 故障代码查询/详情      │ │
│  │ 维护历史    │  │ 库存/草稿  │  │ ChromaDB+fastembed     │ │
│  └────────────┘  └────────────┘  └────────────────────────┘ │
└─────────┬───────────────────────────────────────────────────┘
          │ JSON 文件读取
┌─────────▼───────────────────────────────────────────────────┐
│                    模拟数据层                                │
│  8台设备×336时间点×8测点 | 35条MES工单 | 8份SOP | 15故障代码 │
│  5个产品BOM | 50种物料库存 | 15条维护工单                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 架构设计原则

1. **MCP 标准化**：所有工具通过 MCP 协议暴露，Agent 不直接操作数据，解耦数据层与推理层
2. **OT 层只读**：设备数据全部只读，写操作（创建工单）仅生成草稿，需人工确认
3. **双模式降级**：无 LLM API Key 时自动降级为规则引擎，确保 Demo 可运行
4. **流式优先**：SSE 逐字输出 + 工具调用实时展示，提升用户体感
5. **可观测性**：每个工具调用记录状态、参数、结果摘要，推理链透明

---

## 三、技术选型与依据

### 3.1 选型对比结论

| 维度 | 选型 | 淘汰方案 | 核心依据 |
|------|------|---------|---------|
| MCP 框架 | **FastMCP 2.14** | 官方MCP SDK / ZeroMCP / MiniMCP | 开发效率最高（装饰器API），生态最成熟（7700+项目依赖），性能差距亚毫秒级可忽略 |
| Agent 编排 | **LangGraph 1.2** | CrewAI / AutoGen | Token效率最优，状态机范式精确控制流程，原生interrupt()支持HITL，任务成功率>95.7% |
| RAG 方案 | **轻量自研** | LangChain / LlamaIndex | SOP检索场景简单，ChromaDB+fastembed体积小90%（无torch依赖），延迟<10ms |
| 前端框架 | **Vite+React+TS** | Next.js / Vue | 构建快、HMR流畅、shadcn/ui生态完善、无需SSR |
| UI 组件 | **shadcn/ui** | assistant-ui / Ant Design | 不绑定Vercel AI SDK、可深度定制、工具调用展示最佳 |
| 嵌入模型 | **fastembed(bge-small-zh)** | sentence-transformers | 体积小90%（ONNX方案，无需248MB torch），中文语义检索质量足够 |
| 向量库 | **ChromaDB 1.5** | FAISS / Milvus | 零配置本地持久化，Python原生，Demo阶段最优 |
| 后端框架 | **FastAPI 0.116** | Flask / Django | 原生async、SSE支持好、自动生成OpenAPI文档 |
| A2A 协议 | **暂不引入** | — | 制造业内部单Agent场景足够，多Agent协作需求不明确，后期按需引入 |

### 3.2 为什么不选 A2A

A2A（Agent-to-Agent）协议适用于多 Agent 跨组织协作场景。本项目为制造业内部单 Agent 系统，所有工具在同一信任域内，通过 MCP 协议统一暴露即可。引入 A2A 会增加协议复杂度和网络开销，当前阶段无收益。后期若需跨工厂/跨企业 Agent 协作，可在 MCP 底座之上叠加 A2A 编排层。

---

## 四、核心模块设计

### 4.1 MCP Server 层

共 3 个 MCP Server，18 个工具：

#### 设备 MCP（equipment_mcp.py，6 工具）

| 工具 | 功能 | 参数 |
|------|------|------|
| get_equipment_list | 设备列表 | 无 |
| get_equipment_status | 设备实时状态 | equipment_id |
| get_alarm_equipment | 告警设备列表 | 无 |
| get_equipment_history | 历史趋势 | equipment_id, sensor_id, hours |
| analyze_equipment_anomaly | 异常分析 | equipment_id |
| get_maintenance_history | 维护历史 | equipment_id(可选), limit |

#### MES MCP（mes_mcp.py，7 工具）

| 工具 | 功能 | 参数 |
|------|------|------|
| get_work_orders | 工单列表 | status(可选), line(可选), limit |
| get_work_order_detail | 工单详情 | wo_id |
| get_production_stats | 生产统计 | days |
| get_quality_analysis | 质量分析 | 无 |
| check_material_availability | 物料齐套 | wo_id 或 product_code+quantity |
| get_inventory_summary | 库存概览 | 无 |
| create_work_order_draft | 工单草稿 | product_code, quantity, line |

#### 知识 MCP（knowledge_mcp.py，5 工具）

| 工具 | 功能 | 参数 |
|------|------|------|
| search_sop | SOP 语义搜索 | query, top_k |
| get_sop_detail | SOP 详情 | sop_id |
| list_sop_documents | SOP 列表 | category(可选) |
| search_fault_code | 故障代码查询 | code/equipment/keyword |
| get_fault_code_detail | 故障代码详情 | code |

**RAG 实现细节**：
- 分块策略：按 `## ` 标题切块，保留标题上下文（如"CNC安全操作规程 - 1. 开机前检查"）
- 嵌入模型：BAAI/bge-small-zh-v1.5（fastembed ONNX 方案）
- 向量库：ChromaDB 本地持久化（backend/data/chroma/）
- 去重：按 sop_id 聚合，每个文档只保留最高分段落
- 首次建库：~3s（46个文档块），热启动二次查询：~2-5ms（ChromaDB+fastembed已加载）

### 4.2 Agent 编排层

#### 图结构

```
__start__ → agent(决策/回复) → tools(执行工具) → agent → END
                          ↑                        |
                          └────────────────────────┘
```

#### 双模式运行

**LLM 模式**（配置 OPENAI_API_KEY 时）：
- 使用 langchain-openai 调用 OpenAI 兼容接口
- LLM 自主决策调用哪些工具、传什么参数
- 工具结果返回 LLM 生成最终回复
- recursion_limit=15 防止死循环

**Mock 模式**（无 API Key 时自动降级）：
- 规则引擎通过关键词匹配调度工具
- 模板生成回复，包含实际查询数据
- 覆盖 15+ 场景，7 个 Demo 场景全部支持
- 控制台输出 `[Agent] 未检测到 OPENAI_API_KEY，运行在 Mock 模式`

#### HITL（人工确认）

- 写操作工具集合：`WRITE_TOOLS = {"create_work_order_draft"}`
- 检测到写操作时设置 `pending_confirmation = {"tool": ..., "draft": ...}`
- 草稿不写入系统（status="草稿（待确认）"）
- 前端可展示草稿详情，用户确认后再执行真实写入（预留接口）

#### 工具调用日志

每个工具调用记录：
```json
{
  "tool_call_id": "call_0_1788761592958",
  "tool_name": "get_equipment_status",
  "tool_display": "查询设备实时状态",
  "status": "completed",
  "args": {"equipment_id": "CNC-001"},
  "result_summary": "状态: 告警"
}
```

### 4.3 API 网关层

#### 接口清单

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/health | 健康检查（状态/模式/会话统计） |
| POST | /api/chat/stream | SSE 流式聊天（核心接口） |
| POST | /api/chat | 非流式聊天（一次性返回） |
| GET | /api/equipment/status | 设备状态列表（前端监控面板用） |
| GET | /api/sessions/{id} | 获取会话信息 |
| DELETE | /api/sessions/{id} | 清空会话历史 |
| GET | /api/tools | 列出 18 个工具 |

#### SSE 事件协议

| 事件 | 触发时机 | 数据字段 |
|------|---------|---------|
| start | 会话开始 | session_id, mode, timestamp |
| thinking | LLM 推理中（LLM模式） | message |
| tool_call | 工具调用开始 | tool_call_id, tool, display, status, args |
| tool_result | 工具调用完成 | tool_call_id, tool, display, status, summary |
| token | 逐字输出 | content |
| done | 全部完成 | response, tool_calls, session_id |
| error | 发生错误 | message, type |

#### 会话管理

- 内存存储，TTL 1 小时，保留最近 20 轮对话
- thread-safe（threading.Lock 保护）
- 每 100 次访问触发一次过期会话清理
- session_id 由前端传入或后端自动生成（uuid4）

### 4.4 前端展示层

#### 技术栈

- **构建**：Vite 5 + React 18 + TypeScript 5
- **样式**：TailwindCSS 3 + shadcn/ui 设计规范（CSS 变量主题）
- **图表**：ECharts 5（按需引入，JS 包 657KB）
- **图标**：lucide-react
- **工具**：clsx + tailwind-merge（className 合并）

#### 核心组件

| 组件 | 功能 |
|------|------|
| ChatPanel | 聊天主面板：消息列表 + 输入框 + 快捷提示 + 清空 |
| MessageBubble | 消息气泡：用户/AI 双样式 + 工具调用卡片嵌入 + 思考动画 |
| ToolCallCard | 工具调用卡片：calling/completed/error 三态 + 旋转图标 + 结果摘要 |
| DeviceDashboard | 设备监控：ECharts 温度柱状图 + 状态统计 + 设备列表 + 30秒轮询 |

#### SSE 客户端（useChat Hook）

- Fetch API + ReadableStream 解析 SSE 事件
- Buffer 分块处理，保留不完整行
- 按 tool_call_id 精确匹配工具调用结果
- AbortController 支持停止生成
- thinking 状态三点跳动动画
- 流式光标闪烁效果

---

## 五、模拟数据设计

### 5.1 数据概览

| 数据类型 | 数量 | 文件 |
|---------|------|------|
| 设备时序数据 | 8台 × 336点 × 8测点 | equipment_timeseries.json |
| 设备状态 | 8台 | equipment_status.json |
| MES 工单 | 35条 | mes_work_orders.json |
| SOP 文档 | 8份（Markdown） | sop_documents.json |
| 故障代码 | 15条 | fault_codes.json |
| 产品 BOM | 5个 | product_bom.json |
| 物料库存 | 50种 | inventory.json |
| 维护工单 | 15条 | maintenance_orders.json |

### 5.2 关键数据设计

**设备分布**：7 运行 / 1 告警 / 0 待机
- CNC-001 当前告警：主轴温度 72.61°C（阈值 65°C），主轴振动 4.88mm/s（阈值 4.5mm/s）
- 设备类型：CNC×2、注塑机×2、冲压机×2、装配线×2

**异常注入**：
- CNC-001 温度超阈值持续到当前（实时告警场景）
- INJ-001 历史异常约 168 个点（熔胶温度偏低，最低 125°C），当前已恢复正常
- 3 条异常暂停工单 remark="设备故障待维修"

**库存设计**：
- 故意缺料 5 种（M-0005/0012/0023/0035/0048）
- 呆滞料 3 种（M-0008/0019/0042，8 倍安全库存）
- 低于安全库存 11 种

**数据生成器**：`backend/simulator/generate_data.py`
- 固定随机种子（seed=42），可复现
- 仅用标准库（json/random/math/datetime/pathlib）
- 关联一致性：工单产品⊆BOM产品、BOM物料⊆库存物料、维护设备⊆设备列表

---

## 六、测试与评估

### 6.1 测试设计

- **单轮场景**：7 个场景 × 3 次运行 = 21 次函数调用测试
- **HTTP 端到端**：21 次（通过 POST /api/chat）
- **SSE 流式**：21 次（通过 /api/chat/stream，测量 TTFT）
- **多轮对话**：3 轮连续查询
- **边界输入**：无效设备 ID / 无关查询 / 空消息

### 6.2 评估结果

#### 总体指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 工具调用 Recall | **100.0%** | 7 个场景全部命中预期工具 |
| 工具调用 Precision | **71.4%** | 部分场景调用了额外工具（如设备查询同时调用告警+列表） |
| 平均函数延迟 | **38ms** | Mock 模式纯函数调用，不含 LLM 推理 |
| 平均 HTTP 延迟 | **41ms** | 本地回环，HTTP 开销约 3ms |
| 平均 SSE TTFT | **约 510ms** | 含 0.3s 工具模拟延迟 + 逐字输出启动 |
| 平均回复 Token | **80** | 中文约 1.5 字符/Token 估算 |
| 多轮对话 | **3/3 通过** | 历史传递正确，每轮调用正确工具 |
| 边界测试 | **3/3 通过** | 空消息 400、无效 ID 友好提示、无关查询兜底 |

#### 分场景延迟

| 场景 | 函数延迟 | HTTP延迟 | TTFT | 工具数 | Recall | Precision |
|------|---------|---------|------|--------|--------|-----------|
| S1 设备查询 | 37ms | 39ms | 638ms | 2 | 100% | 50% |
| S2 SOP检索 | 3ms | 4ms | 301ms | 1 | 100% | 100% |
| S3 异常诊断 | 35ms | 39ms | 635ms | 2 | 100% | 50% |
| S4 预测维护 | 68ms | 65ms | 660ms | 2 | 100% | 50% |
| S5 工单分析 | 20ms | 25ms | 324ms | 1 | 100% | 100% |
| S6 物料齐套 | 67ms | 75ms | 662ms | 2 | 100% | 50% |
| S7 工单草稿 | 38ms | 39ms | 339ms | 1 | 100% | 100% |

> 注：TTFT（首字延迟）较高是因为 Mock 模式下每个工具调用前有 0.3s 模拟延迟，用于展示工具调用卡片动画。真实 LLM 模式下 TTFT 主要取决于 LLM 首 token 延迟（通常 1-3 秒）。

### 6.3 测试条件说明

- ChromaDB/fastembed 热启动（测试前执行一次预热查询）
- 首次冷启动 RAG 延迟预计 500-2000ms（含模型加载+索引构建）
- Mock 模式延迟极低，真实 LLM 模式延迟会增加 2-10 秒（取决于模型和网络）

---

## 七、部署指南

### 7.1 环境要求

- Python 3.12+
- Node.js 18+（前端构建）
- 磁盘空间：>500MB（含依赖和模型）

### 7.2 后端启动

```bash
cd backend
pip install fastmcp chromadb fastembed fastapi uvicorn langgraph langchain-core langchain-openai sse-starlette python-multipart pydantic

# 生成模拟数据
python simulator/generate_data.py

# 启动服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**LLM 模式**（可选）：
```bash
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 或兼容接口
export OPENAI_MODEL="gpt-4o-mini"
```

### 7.3 前端启动

```bash
cd frontend
npm install
npm run dev    # 开发模式，http://localhost:5173
npm run build  # 生产构建，输出到 dist/
```

Vite 开发服务器自动代理 `/api` → `http://localhost:8000`。

### 7.4 项目结构

```
manufacturing-ai-agent-demo/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── sessions.py          # 会话管理
│   ├── agent/               # LangGraph Agent 编排
│   │   ├── graph.py         # 图构建 + 双模式运行
│   │   ├── tools.py         # 18个工具注册
│   │   ├── state.py         # 状态定义
│   │   └── prompts.py       # 系统提示词
│   ├── mcp_servers/         # 3个 MCP Server
│   │   ├── equipment_mcp.py # 设备工具(6)
│   │   ├── mes_mcp.py       # MES工具(7)
│   │   └── knowledge_mcp.py # 知识RAG工具(5)
│   ├── simulator/
│   │   └── generate_data.py # 模拟数据生成器
│   └── data/                # JSON数据文件(8个) + chroma/
├── frontend/
│   ├── src/
│   │   ├── components/      # ChatPanel/MessageBubble/ToolCallCard/DeviceDashboard
│   │   ├── hooks/useChat.ts # SSE客户端Hook
│   │   ├── types/           # TypeScript类型定义
│   │   └── lib/utils.ts     # 工具函数
│   └── package.json
├── tests/
│   └── run_evaluation.py    # 自动化测试评估脚本
├── docs/
│   ├── research-report.md   # 调研报告(v1.2)
│   ├── technical-report.md  # 本技术报告
│   └── evaluation-results.json # 评估结果数据
├── README.md
├── LICENSE                  # MIT
└── .gitignore
```

### 7.5 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 端口 8000 被占用 | 其他进程占用 | `lsof -i :8000` 查找并 kill，或改用 `--port 8001` |
| pip 安装失败 | 网络超时 | 使用国内镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| npm install 超时 | 网络问题 | 使用国内镜像：`npm config set registry https://registry.npmmirror.com` |
| ChromaDB 初始化失败 | 索引损坏 | 删除 `backend/data/chroma/` 目录，重启服务自动重建 |
| 前端请求 404 | 后端未启动或代理配置错误 | 确认后端运行在 8000 端口，检查 `vite.config.ts` 代理配置 |
| RAG 搜索无结果 | 索引未构建 | 首次运行需等待 3s 建库，或删除 chroma 目录重启 |
| Mock 模式警告 | 未配置 API Key | 正常现象，配置 `OPENAI_API_KEY` 后自动切换 LLM 模式 |

---

## 八、后续优化方向

### 8.1 短期优化

1. **真实 LLM 接入验证**：配置 OpenAI API Key，验证 LLM 模式下的工具调度准确率和回复质量
2. **工具调用 Precision 优化**：减少冗余调用（如设备查询同时调用告警+列表可合并）
3. **RAG 检索质量提升**：查询扩展、混合检索（语义+BM25）、重排序
4. **前端构建优化**：ECharts 动态 import，首屏 JS 降到 300KB 以内
5. **日志与监控体系建设**：添加结构化日志、请求追踪、性能指标采集，便于线上排查

### 8.2 中期优化

1. **真实系统对接**：将 MCP Server 从 JSON 文件读取改为对接真实 MES/SCADA/ERP API
2. **写操作 HITL 闭环**：工单草稿确认后真实写入 MES 系统
3. **持久化会话**：从内存存储改为 Redis/数据库，支持服务重启恢复
4. **用户认证**：添加登录鉴权，按角色限制工具权限
5. **多轮对话优化**：LLM 模式下的上下文压缩、摘要记忆

### 8.3 长期规划

1. **A2A 多 Agent 协作**：跨工厂/跨企业 Agent 协作，在 MCP 底座上叠加 A2A 编排层
2. **主动告警推送**：设备异常时主动推送通知，而非被动查询
3. **预测性维护模型**：基于时序数据训练异常检测模型，提前预警设备故障
4. **知识库自动更新**：SOP 文档版本管理、增量索引、自动同步
5. **移动端适配**：PWA 支持，车间平板/手机端可用

---

## 九、总结

本项目构建了一个完整的制造业内部系统智能化 AI Agent Demo，覆盖从数据层、MCP 工具层、Agent 编排层、API 网关层到前端展示层的全链路实现。核心特点：

- **MCP 标准化**：18 个工具通过 FastMCP 暴露，解耦数据与推理
- **LangGraph 编排**：状态机范式精确控制流程，双模式运行确保可演示
- **SSE 流式体验**：逐字输出 + 工具调用实时展示，TTFT 约 510ms
- **安全可控**：OT 层只读，写操作 HITL 待确认
- **可观测**：推理链透明，每个工具调用记录状态和结果
- **可扩展**：新增系统只需添加 MCP Server，Agent 自动发现可用工具

测试评估表明：7 个 Demo 场景工具调用 Recall 100%，多轮对话 3/3 通过，边界测试 3/3 通过，系统稳定可靠。

---

*报告结束 · v1.0*
