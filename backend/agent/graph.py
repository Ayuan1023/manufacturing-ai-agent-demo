"""
LangGraph Agent 编排层
支持真实 LLM 调用和 Mock 模式（无 API Key 时自动降级）
"""
import os
import json
import re
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END

from .state import AgentState
from .prompts import SYSTEM_PROMPT
from .tools import get_all_tools, WRITE_TOOLS, TOOL_DESCRIPTIONS

# 全局工具列表
TOOLS = get_all_tools()
TOOL_MAP = {t.name: t for t in TOOLS}


def _get_llm():
    """
    初始化 LLM，支持 OpenAI 兼容接口
    环境变量：OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL
    无 API Key 时返回 None（使用 Mock 模式）
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
        base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
            streaming=True,
        )
    except Exception as e:
        print(f"[Agent] LLM 初始化失败，使用 Mock 模式: {e}")
        return None


LLM = _get_llm()
IS_MOCK = LLM is None

if IS_MOCK:
    print("[Agent] 未检测到 OPENAI_API_KEY，运行在 Mock 模式（规则引擎调度工具）")


# ============ 工具函数：从文本提取参数 ============

def _extract_wo_id(text: str) -> str | None:
    """从文本中提取工单号"""
    m = re.search(r"wo-\d+-\d+", text, re.IGNORECASE)
    return m.group(0).upper() if m else None


def _extract_equipment_id(text: str) -> str | None:
    """从文本中提取设备ID"""
    m = re.search(r"(cnc|inj|prs|asm)-\d+", text, re.IGNORECASE)
    return m.group(0).upper() if m else None


def _extract_product_code(text: str) -> str | None:
    """从文本中提取产品编码"""
    m = re.search(r"p-[a-z]\d+", text, re.IGNORECASE)
    return m.group(0).upper() if m else None


def _extract_quantity(text: str) -> int | None:
    """从文本中提取数量"""
    m = re.search(r"(\d+)\s*(件|个|套|台|pcs)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"[×x*]\s*(\d+)", text)
    if m:
        return int(m.group(1))
    return None


# ============ Mock 模式：规则引擎 ============

# 创建工单的正则模式（统一使用，避免排除条件和触发条件不一致）
CREATE_WO_PATTERN = r"创建.*工单|新建.*工单|开.*工单|下.*生产单|安排生产|新增工单"


def _mock_tool_decision(user_input: str) -> list[dict]:
    """
    Mock 模式下根据用户输入关键词决定调用哪些工具
    返回工具调用列表
    """
    text = user_input.lower()
    calls = []

    # ===== SOP/知识相关（优先匹配）=====
    if any(k in text for k in [
        "sop", "操作规程", "怎么操作", "操作步骤", "规范", "怎么处理",
        "怎么办", "如何处理", "处理方法", "换模", "换刀", "调试",
        "校准", "保养步骤", "开机步骤", "关机步骤", "步骤",
    ]):
        calls.append({"name": "search_sop", "args": {"query": user_input, "top_k": 3}})

    # ===== 故障代码相关 =====
    if re.search(r"e\d{3}", text) or any(k in text for k in ["故障代码", "报警代码", "错误代码", "报错代码"]):
        code_match = re.search(r"e\d{3}", text, re.IGNORECASE)
        code = code_match.group(0).upper() if code_match else "E001"
        calls.append({"name": "search_fault_code", "args": {"code": code}})

    # ===== 设备相关 =====
    if any(k in text for k in ["告警", "异常", "故障", "报警", "哪里有问题", "有什么问题", "设备问题"]):
        calls.append({"name": "get_alarm_equipment", "args": {}})

    eq_id = _extract_equipment_id(text)
    if eq_id:
        if any(k in text for k in ["状态", "实时", "情况", "怎么样", "数据", "读数", "参数"]):
            calls.append({"name": "get_equipment_status", "args": {"equipment_id": eq_id}})
        if any(k in text for k in ["趋势", "历史", "最近", "变化", "曲线", "波动"]):
            sensor = "spindle_temp" if "温度" in text else "power"
            calls.append({"name": "get_equipment_history", "args": {"equipment_id": eq_id, "sensor_id": sensor, "hours": 24}})
        if any(k in text for k in ["分析", "诊断", "检查", "检测"]):
            calls.append({"name": "analyze_equipment_anomaly", "args": {"equipment_id": eq_id}})
        if any(k in text for k in ["维护", "维修", "修过", "保养记录"]):
            calls.append({"name": "get_maintenance_history", "args": {"equipment_id": eq_id, "limit": 5}})

    if any(k in text for k in ["维护记录", "维修历史", "所有维护", "维护统计"]) and not eq_id:
        calls.append({"name": "get_maintenance_history", "args": {"limit": 10}})

    if any(k in text for k in ["设备列表", "有哪些设备", "产线设备", "所有设备", "设备清单"]):
        calls.append({"name": "get_equipment_list", "args": {}})

    # ===== 工单/生产相关 =====
    wo_id = _extract_wo_id(text)
    if wo_id:
        calls.append({"name": "get_work_order_detail", "args": {"wo_id": wo_id}})
    elif any(k in text for k in ["工单", "生产单", "生产任务"]) and not re.search(CREATE_WO_PATTERN, text):
        calls.append({"name": "get_work_orders", "args": {"limit": 10}})

    if any(k in text for k in ["生产统计", "生产情况", "产量", "完成率", "生产数据", "本周生产", "本月生产", "产能", "生产进度"]):
        calls.append({"name": "get_production_stats", "args": {"days": 7}})

    if any(k in text for k in ["质量", "良率", "不良", "合格率", "废品", "不良率"]):
        calls.append({"name": "get_quality_analysis", "args": {}})

    # ===== 物料相关 =====
    if any(k in text for k in ["物料齐套", "齐套", "能不能投产", "够不够生产", "物料够吗", "齐套检查"]):
        check_wo = wo_id or "WO-2026-0001"
        calls.append({"name": "check_material_availability", "args": {"wo_id": check_wo}})

    if any(k in text for k in ["库存", "缺料", "呆滞", "物料情况", "物料库存", "仓库", "库存盘点"]):
        calls.append({"name": "get_inventory_summary", "args": {}})

    # ===== 创建工单（用正则匹配变体）=====
    if re.search(CREATE_WO_PATTERN, text):
        product = _extract_product_code(text) or "P-A100"
        qty = _extract_quantity(text) or 500
        line = "1号线"
        if "2号" in text or "二号线" in text:
            line = "2号线"
        elif "3号" in text or "三号线" in text:
            line = "3号线"
        elif "4号" in text or "四号线" in text:
            line = "4号线"
        calls.append({"name": "create_work_order_draft", "args": {
            "product_code": product, "quantity": qty, "line": line, "priority": "中",
        }})

    # ===== 默认：设备概览 =====
    if not calls:
        calls.append({"name": "get_equipment_list", "args": {}})
        calls.append({"name": "get_alarm_equipment", "args": {}})

    # 去重（保留顺序）
    seen = set()
    unique_calls = []
    for c in calls:
        key = c["name"] + json.dumps(c["args"], sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique_calls.append(c)

    return unique_calls


def _mock_generate_response(user_input: str, tool_results: list[dict]) -> str:
    """Mock 模式下根据工具结果生成回复"""
    parts = ["根据查询结果，为您汇总如下：\n"]
    fault_section = []
    sop_section = []

    for tr in tool_results:
        name = tr["name"]
        data = tr["result"]

        # 统一错误检查
        if isinstance(data, dict) and "error" in data:
            parts.append(f"⚠️ {TOOL_DESCRIPTIONS.get(name, name)}查询失败：{data.get('error', '未知错误')}")
            continue

        if name == "get_alarm_equipment":
            alarm_count = data.get("alarm_count", 0)
            if alarm_count > 0:
                for eq in data.get("equipment", []):
                    parts.append(f"🔴 **{eq.get('name', '未知设备')}**（{eq.get('line', '')}）存在告警：")
                    for s in eq.get("alarm_sensors", []):
                        parts.append(f"  - {s.get('sensor', '')}: {s.get('value', '')}{s.get('unit', '')}（阈值{s.get('threshold', '')}{s.get('unit', '')}，超出{s.get('exceed_pct', '')}%）")
            else:
                parts.append("🟢 当前无设备告警")

        elif name == "get_equipment_status":
            status = data.get("status", "未知")
            status_icon = "🔴" if status == "告警" else "🟢" if status == "运行" else "🟡"
            parts.append(f"{status_icon} **{data.get('name', '未知设备')}** 当前状态：{status}")
            if data.get("alarms"):
                parts.append("告警测点：")
                for a in data["alarms"]:
                    parts.append(f"  - {a.get('sensor', '')}: {a.get('value', '')}{a.get('unit', '')}（阈值{a.get('threshold', '')}{a.get('unit', '')}）")

        elif name == "get_equipment_list":
            equipment = data.get("equipment", [])
            parts.append(f"📋 **设备列表**（共{data.get('total', len(equipment))}台）：")
            for eq in equipment[:8]:
                icon = "🔴" if eq.get("status") == "告警" else "🟢" if eq.get("status") == "运行" else "🟡"
                parts.append(f"  {icon} {eq.get('id', '')} | {eq.get('name', '')} | {eq.get('line', '')} | {eq.get('status', '')}")

        elif name == "get_equipment_history":
            stats = data.get("statistics", {})
            parts.append(f"📈 **{data.get('sensor_name', '')}趋势**（最近{data.get('hours', 24)}小时）：")
            parts.append(f"  - 最新值: {stats.get('latest', '')}{data.get('unit', '')}")
            parts.append(f"  - 范围: {stats.get('min', '')}~{stats.get('max', '')}{data.get('unit', '')}")
            parts.append(f"  - 平均值: {stats.get('avg', '')}{data.get('unit', '')}")
            parts.append(f"  - 趋势: {stats.get('trend', '')}")

        elif name == "get_production_stats":
            parts.append(f"📊 **生产统计**（最近{data.get('period_days', 7)}天）：")
            parts.append(f"  - 工单完成率：{data.get('completion_rate', 0)}%")
            parts.append(f"  - 计划产量：{data.get('total_planned_qty', 0)}，已完成：{data.get('total_completed_qty', 0)}")
            parts.append(f"  - 平均良率：{data.get('avg_yield_rate', 0)}%")
            parts.append(f"  - 状态分布：{data.get('status_distribution', {})}")

        elif name == "get_quality_analysis":
            dist = data.get("yield_distribution", {})
            parts.append(f"📈 **质量分析**：")
            parts.append(f"  - 整体平均良率：{data.get('overall_avg_yield', 0)}%（目标{data.get('quality_target', 98)}%）")
            parts.append(f"  - 分布：优秀{dist.get('excellent(>=98%)', 0)} / 良好{dist.get('good(95-98%)', 0)} / 偏低{dist.get('poor(<95%)', 0)}")
            if data.get("low_yield_orders"):
                parts.append("  - 低良率工单：")
                for o in data["low_yield_orders"][:3]:
                    parts.append(f"    * {o.get('wo_id', '')}: {o.get('yield_rate', '')}%")

        elif name == "get_inventory_summary":
            parts.append(f"📦 **库存概览**：")
            parts.append(f"  - 物料总数：{data.get('total_materials', 0)}")
            parts.append(f"  - ⚠️ 缺料预警：{data.get('shortage_count', 0)}种")
            parts.append(f"  - 呆滞料：{data.get('dormant_count', 0)}种")
            parts.append(f"  - 在途物料：{data.get('in_transit_count', 0)}种")

        elif name == "check_material_availability":
            icon = "✅" if data.get("overall_status") == "齐套" else "❌"
            parts.append(f"{icon} **物料齐套检查**（{data.get('product_name', '')} × {data.get('quantity', 0)}）：")
            parts.append(f"  - 整体状态：{data.get('overall_status', '未知')}")
            parts.append(f"  - 齐套项：{data.get('ready_items', 0)}/{data.get('total_items', 0)}")
            if data.get("shortage_items"):
                parts.append("  - 缺料明细：")
                for s in data["shortage_items"]:
                    parts.append(f"    * {s.get('mat_name', '')}: 需{s.get('required', 0)}，可用{s.get('available', 0)}，缺{s.get('shortage', 0)}")

        elif name == "search_sop":
            results = data.get("results", [])
            if results:
                sop_section.append("📚 **SOP 检索结果**：")
                for r in results:
                    sop_section.append(f"  {r.get('rank', '')}. [{r.get('similarity', 0)}%] {r.get('title', '')}（{r.get('category', '')}）")

        elif name == "search_fault_code":
            faults = data.get("faults", [])
            if faults:
                fault_section.append("⚠️ **故障代码详情**：")
                for f in faults:
                    fault_section.append(f"  - **{f.get('code', '')} {f.get('name', '')}**（严重度：{f.get('severity', '')}）")
                    fault_section.append(f"    原因：{f.get('cause', '')}")
                    fault_section.append(f"    处理：{f.get('action', '')}")

        elif name == "analyze_equipment_anomaly":
            parts.append(f"🔍 **{data.get('equipment_name', '')} 异常分析**：")
            parts.append(f"  - 综合严重度：{data.get('overall_severity', '未知')}")
            for f in data.get("findings", []):
                parts.append(f"  - [{f.get('severity', '')}] {f.get('sensor', '')}: {f.get('issue', '')}")
                parts.append(f"    建议：{f.get('suggestion', '')}")
            parts.append(f"  - 总体建议：{data.get('recommendation', '')}")

        elif name == "get_maintenance_history":
            parts.append(f"🔧 **维护历史**（共{data.get('total_orders', 0)}条）：")
            parts.append(f"  - 总停机时长：{data.get('total_downtime_hours', 0)}小时")
            parts.append(f"  - 总维护费用：¥{data.get('total_cost', 0)}")
            for o in data.get("orders", [])[:3]:
                parts.append(f"  - {o.get('mo_id', '')}: {o.get('equipment_name', '')} - {str(o.get('fault_description', ''))[:30]}")

        elif name == "get_work_orders":
            orders = data.get("orders", [])
            parts.append(f"📋 **工单列表**（共{data.get('total', 0)}条）：")
            for o in orders[:5]:
                icon = "🔴" if o.get("status") == "异常暂停" else "🟢" if o.get("status") == "已完成" else "🔵"
                parts.append(f"  {icon} {o.get('wo_id', '')} | {o.get('product_name', '')} | {o.get('status', '')} | 进度{o.get('completed', 0)}/{o.get('quantity', 0)}")

        elif name == "get_work_order_detail":
            parts.append(f"📋 **工单详情 {data.get('wo_id', '')}**：")
            parts.append(f"  - 产品：{data.get('product_name', '')} × {data.get('quantity', 0)}")
            parts.append(f"  - 状态：{data.get('status', '')}，进度：{data.get('progress_pct', 0)}%")
            parts.append(f"  - 良率：{data.get('yield_rate', 'N/A')}%")
            parts.append(f"  - 产线：{data.get('line', '')}，操作员：{data.get('operator', '')}")

        elif name == "create_work_order_draft":
            draft = data.get("draft", {})
            parts.append("📝 **工单草稿已生成**（需人工确认）：")
            parts.append(f"  - 工单号：{draft.get('wo_id', '')}")
            parts.append(f"  - 产品：{draft.get('product_name', '')} × {draft.get('quantity', 0)}")
            parts.append(f"  - 产线：{draft.get('line', '')}，优先级：{draft.get('priority', '')}")
            parts.append(f"  - 工艺路线：{draft.get('process_route', '')}")
            parts.append("  - ⚠️ 此为草稿，确认后才会提交至MES系统")

        elif name == "get_sop_detail":
            parts.append(f"📖 **{data.get('title', '')}**：")
            content = data.get("content", "")
            parts.append(content[:500] + ("..." if len(content) > 500 else ""))

        elif name == "list_sop_documents":
            parts.append(f"📚 **SOP文档列表**（共{data.get('total', 0)}份）：")
            for d in data.get("documents", []):
                parts.append(f"  - {d.get('id', '')}: {d.get('title', '')}（{d.get('category', '')}）")

        elif name == "get_fault_code_detail":
            parts.append(f"⚠️ **故障代码 {data.get('code', '')}**：{data.get('name', '')}")
            parts.append(f"  - 严重度：{data.get('severity', '')}")
            parts.append(f"  - 原因：{data.get('cause', '')}")
            parts.append(f"  - 处理：{data.get('action', '')}")

    # 故障代码和SOP分区展示
    if fault_section:
        parts.extend(fault_section)
    if sop_section:
        parts.extend(sop_section)

    if len(parts) <= 1:
        parts.append("已查询相关数据，以上为汇总结果。如需更详细的信息，请告诉我具体关注的方面。")

    return "\n".join(parts)


# ============ LangGraph 节点 ============

def agent_node(state: AgentState) -> AgentState:
    """Agent 推理节点：调用 LLM 或 Mock 引擎决定下一步"""
    messages = state["messages"]
    tool_calls_log = state.get("tool_calls_log", [])

    if IS_MOCK:
        # 找到最后一条 HumanMessage
        last_human_idx = None
        for i, m in enumerate(messages):
            if isinstance(m, HumanMessage):
                last_human_idx = i

        # 只检查最后一条 HumanMessage 之后是否有 ToolMessage（本轮的工具结果）
        messages_after_human = messages[last_human_idx + 1:] if last_human_idx is not None else []
        has_tool_results_this_round = any(isinstance(m, ToolMessage) for m in messages_after_human)

        last_human = messages[last_human_idx] if last_human_idx is not None else None
        user_input = last_human.content if last_human else ""

        if has_tool_results_this_round:
            # 本轮已有工具结果，生成最终回复
            tool_results = []
            for tm in messages_after_human:
                if isinstance(tm, ToolMessage):
                    try:
                        result = json.loads(tm.content) if isinstance(tm.content, str) else tm.content
                    except (json.JSONDecodeError, TypeError):
                        result = {"raw": tm.content}
                    tool_results.append({"name": tm.name, "result": result})
            response = _mock_generate_response(user_input, tool_results)

            # 检查是否有待确认的写操作（HITL）
            pending = None
            for tr in tool_results:
                if tr["name"] == "create_work_order_draft" and isinstance(tr["result"], dict):
                    draft = tr["result"].get("draft", {})
                    if draft:
                        pending = {"tool": "create_work_order_draft", "draft": draft}
                        break

            return {
                "messages": [AIMessage(content=response)],
                "tool_calls_log": tool_calls_log,
                "pending_confirmation": pending,
            }

        # 第一轮：决定调用工具
        tool_calls = _mock_tool_decision(user_input)
        ai_msg = AIMessage(
            content="正在查询相关数据...",
            tool_calls=[{"id": f"call_{i}", "name": tc["name"], "args": tc["args"]} for i, tc in enumerate(tool_calls)],
        )

        for i, tc in enumerate(tool_calls):
            tool_calls_log.append({
                "tool_call_id": f"call_{i}",
                "tool_name": tc["name"],
                "tool_display": TOOL_DESCRIPTIONS.get(tc["name"], tc["name"]),
                "args": tc["args"],
                "status": "calling",
            })

        return {"messages": [ai_msg], "tool_calls_log": tool_calls_log}

    else:
        # 真实 LLM 模式
        system_msg = SystemMessage(content=SYSTEM_PROMPT)
        all_messages = [system_msg] + list(messages)
        llm_with_tools = LLM.bind_tools(TOOLS)
        response = llm_with_tools.invoke(all_messages)

        if response.tool_calls:
            for tc in response.tool_calls:
                tool_calls_log.append({
                    "tool_call_id": tc.get("id", ""),
                    "tool_name": tc["name"],
                    "tool_display": TOOL_DESCRIPTIONS.get(tc["name"], tc["name"]),
                    "args": tc["args"],
                    "status": "calling",
                })

        return {"messages": [response], "tool_calls_log": tool_calls_log}


def tool_execution_node(state: AgentState) -> AgentState:
    """工具执行节点：执行 AI 消息中的所有 tool_calls"""
    messages = state["messages"]
    tool_calls_log = state.get("tool_calls_log", [])

    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage) and m.tool_calls), None)
    if not last_ai:
        return {"messages": [], "tool_calls_log": tool_calls_log}

    tool_messages = []
    for tc in last_ai.tool_calls:
        tool_name = tc["name"]
        tool_args = tc.get("args", {})
        tool_id = tc.get("id", f"call_{tool_name}")

        tool = TOOL_MAP.get(tool_name)
        if tool:
            try:
                result = tool.invoke(tool_args)
                content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
            except Exception as e:
                content = json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)
        else:
            content = json.dumps({"error": f"工具 {tool_name} 不存在"}, ensure_ascii=False)

        tool_messages.append(ToolMessage(content=content, name=tool_name, tool_call_id=tool_id))

        # 用 tool_call_id 精确匹配日志
        for log in tool_calls_log:
            if log.get("tool_call_id") == tool_id and log["status"] == "calling":
                log["status"] = "completed"
                try:
                    result_data = json.loads(content) if isinstance(content, str) else content
                    log["result_summary"] = _summarize_result(tool_name, result_data)
                except Exception:
                    log["result_summary"] = "执行完成"
                break

    return {"messages": tool_messages, "tool_calls_log": tool_calls_log}


def _summarize_result(tool_name: str, data: dict) -> str:
    """生成工具结果摘要（用于前端展示），覆盖全部18个工具"""
    if isinstance(data, dict) and "error" in data:
        return f"错误: {data.get('error', '未知')}"

    summaries = {
        "get_equipment_list": f"{data.get('total', 0)}台设备",
        "get_equipment_status": f"状态: {data.get('status', '未知')}",
        "get_alarm_equipment": f"{data.get('alarm_count', 0)}台设备告警",
        "get_equipment_history": f"{data.get('sensor_name', '')} {data.get('statistics', {}).get('trend', '')}",
        "analyze_equipment_anomaly": f"严重度: {data.get('overall_severity', '未知')}",
        "get_maintenance_history": f"{data.get('total_orders', 0)}条维护记录",
        "get_work_orders": f"{data.get('total', 0)}条工单",
        "get_work_order_detail": f"{data.get('status', '')} 进度{data.get('progress_pct', 0)}%",
        "get_production_stats": f"完成率{data.get('completion_rate', 0)}%, 良率{data.get('avg_yield_rate', 0)}%",
        "get_quality_analysis": f"平均良率{data.get('overall_avg_yield', 0)}%",
        "check_material_availability": f"物料{data.get('overall_status', '未知')}",
        "get_inventory_summary": f"{data.get('total_materials', 0)}种物料, {data.get('shortage_count', 0)}种缺料",
        "create_work_order_draft": f"草稿{data.get('draft', {}).get('wo_id', '')}已生成",
        "search_sop": f"找到{data.get('result_count', 0)}份SOP",
        "get_sop_detail": f"{data.get('title', '')}",
        "list_sop_documents": f"{data.get('total', 0)}份SOP文档",
        "search_fault_code": f"{data.get('total', 0)}条故障代码",
        "get_fault_code_detail": f"{data.get('code', '')}: {data.get('name', '')}",
    }
    return summaries.get(tool_name, "查询完成")


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """条件边：判断是否需要继续调用工具"""
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "end"


# ============ 构建图 ============

def build_graph():
    """构建并编译 LangGraph"""
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_execution_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile()


GRAPH = build_graph()


def run_agent(user_input: str, history: list = None) -> dict:
    """
    运行 Agent，返回完整的执行结果

    参数:
        user_input: 用户输入
        history: 历史消息列表

    返回:
        {
            "response": str,
            "tool_calls": list[dict],
            "pending_confirmation": dict | None,
        }
    """
    messages = []
    if history:
        messages.extend(history)
    messages.append(HumanMessage(content=user_input))

    initial_state = AgentState(
        messages=messages,
        pending_confirmation=None,
        tool_calls_log=[],
    )

    # 设置最大迭代次数，防止死循环
    result = GRAPH.invoke(initial_state, config={"recursion_limit": 15})

    final_response = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_response = msg.content
            break

    return {
        "response": final_response,
        "tool_calls": result.get("tool_calls_log", []),
        "pending_confirmation": result.get("pending_confirmation"),
    }
