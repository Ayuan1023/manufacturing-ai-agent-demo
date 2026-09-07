"""
FastAPI 后端入口
提供 SSE 流式聊天接口、会话管理、健康检查
"""
import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent))


DATA_DIR = Path(__file__).parent / "data"
REQUIRED_DATA_FILES = {
    "equipment_status.json",
    "equipment_timeseries.json",
    "fault_codes.json",
    "inventory.json",
    "maintenance_orders.json",
    "mes_work_orders.json",
    "product_bom.json",
    "sop_documents.json",
}


def ensure_demo_data():
    """Generate the deterministic local dataset on a fresh clone."""
    if REQUIRED_DATA_FILES.issubset({path.name for path in DATA_DIR.glob("*.json")}):
        return

    from simulator.generate_data import (
        generate_bom_and_inventory,
        generate_equipment_timeseries,
        generate_maintenance_orders,
        generate_sop_docs,
        generate_work_orders,
    )

    generate_equipment_timeseries()
    generate_work_orders()
    generate_sop_docs()
    generate_bom_and_inventory()
    generate_maintenance_orders()


ensure_demo_data()

from agent.graph import (
    _mock_tool_decision,
    _mock_generate_response,
    _summarize_result,
    run_agent,
    TOOL_MAP,
    IS_MOCK,
)
from agent.tools import TOOL_DESCRIPTIONS
from sessions import session_manager

app = FastAPI(
    title="制造业智能运维 Agent API",
    description="基于 MCP + LangGraph 的制造业 AI Agent Demo",
    version="1.0.0",
)

# Demo 阶段全开放 CORS，生产环境应限制为前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 请求模型 ============

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000, description="用户消息，最多2000字符")
    session_id: str | None = Field(None, description="会话ID，不传则自动生成")


# ============ SSE 工具函数 ============

def sse_event(event_type: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def execute_tool_sync(tool_name: str, args: dict) -> dict:
    """同步执行单个工具"""
    tool = TOOL_MAP.get(tool_name)
    if not tool:
        return {"error": f"工具 {tool_name} 不存在"}
    try:
        result = tool.invoke(args)
        return result if isinstance(result, dict) else {"raw": str(result)}
    except Exception as e:
        return {"error": f"工具执行失败: {str(e)}"}


# ============ 统一 Agent 流式执行 ============

async def execute_agent_stream(message: str, session_id: str):
    """
    统一的 Agent 流式执行入口
    - Mock 模式：规则引擎决策 + 逐个执行工具 + 模板生成回复
    - LLM 模式：调用 run_agent（经过 LangGraph 图）+ 逐字推送
    两种模式都使用会话历史，输出统一的 SSE 事件流
    """
    history = session_manager.get_history(session_id)

    if IS_MOCK:
        # ===== Mock 模式：规则引擎 =====
        tool_calls = _mock_tool_decision(message)
        tool_results = []

        for idx, tc in enumerate(tool_calls):
            tool_name = tc["name"]
            tool_args = tc["args"]
            display = TOOL_DESCRIPTIONS.get(tool_name, tool_name)
            call_id = f"call_{idx}_{int(time.time()*1000)}"

            yield sse_event("tool_call", {
                "tool_call_id": call_id,
                "tool": tool_name, "display": display,
                "status": "calling", "args": tool_args,
            })

            # 异步 sleep，不阻塞事件循环
            await asyncio.sleep(0.3)

            # 工具执行（同步操作，用 run_in_executor 避免阻塞）
            result = await asyncio.get_event_loop().run_in_executor(
                None, execute_tool_sync, tool_name, tool_args
            )
            tool_results.append({"name": tool_name, "result": result})

            summary = _summarize_result(tool_name, result)
            yield sse_event("tool_result", {
                "tool_call_id": call_id,
                "tool": tool_name, "display": display,
                "status": "completed", "summary": summary,
            })

        # 生成回复
        response = _mock_generate_response(message, tool_results)
        tool_calls_log = [
            {"tool": tc["name"], "display": TOOL_DESCRIPTIONS.get(tc["name"], tc["name"]), "args": tc["args"]}
            for tc in tool_calls
        ]

    else:
        # ===== LLM 模式：LangGraph 图执行 =====
        # 推送 thinking 事件 + SSE keep-alive 注释行，防止连接超时
        yield sse_event("thinking", {"message": "正在调用 LLM 推理..."})
        yield ": keep-alive\n\n"

        result = await asyncio.get_event_loop().run_in_executor(
            None, run_agent, message, history
        )

        response = result["response"]
        tool_calls_log = result.get("tool_calls", [])

        # 推送工具调用事件（LLM 模式下工具已在图中执行完）
        for tc in tool_calls_log:
            yield sse_event("tool_call", {
                "tool": tc.get("tool_name", ""),
                "display": tc.get("tool_display", ""),
                "status": tc.get("status", "completed"),
                "args": tc.get("args", {}),
            })
            yield sse_event("tool_result", {
                "tool": tc.get("tool_name", ""),
                "display": tc.get("tool_display", ""),
                "status": "completed",
                "summary": tc.get("result_summary", ""),
            })

    # ===== 通用：逐字推送回复 =====
    for char in response:
        yield sse_event("token", {"content": char})
        await asyncio.sleep(0.01)

    # 保存到会话历史
    session_manager.add_messages(session_id, message, response)

    # 完成事件
    yield sse_event("done", {
        "response": response,
        "tool_calls": tool_calls_log,
        "session_id": session_id,
    })


# ============ SSE 聊天接口（带全局错误处理）============

async def chat_stream_generator(message: str, session_id: str):
    """SSE 流式聊天生成器，带全局错误处理"""
    try:
        # 开始事件
        yield sse_event("start", {
            "session_id": session_id,
            "mode": "mock" if IS_MOCK else "llm",
            "timestamp": time.time(),
        })

        # 执行 Agent 流式逻辑
        async for event in execute_agent_stream(message, session_id):
            yield event

    except Exception as e:
        # 全局错误处理：推送 error 事件后正常结束流
        yield sse_event("error", {"message": str(e), "type": type(e).__name__})
        yield sse_event("done", {"error": str(e), "session_id": session_id})


# ============ 路由 ============

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "mode": "mock" if IS_MOCK else "llm",
        "version": "1.0.0",
        "sessions": session_manager.get_stats(),
    }


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式聊天接口"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    session_id = request.session_id or str(uuid.uuid4())
    return StreamingResponse(
        chat_stream_generator(request.message, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """非流式聊天接口（一次性返回）"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    session_id = request.session_id or str(uuid.uuid4())
    history = session_manager.get_history(session_id)
    result = run_agent(request.message, history=history)
    session_manager.add_messages(session_id, request.message, result["response"])
    return {
        "response": result["response"],
        "tool_calls": result["tool_calls"],
        "pending_confirmation": result["pending_confirmation"],
        "session_id": session_id,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    session = session_manager.get_or_create(session_id)
    return {
        "session_id": session_id,
        "message_count": session["message_count"],
        "created_at": session["created_at"],
        "last_active": session["last_active"],
    }


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str):
    """清空会话历史"""
    session_manager.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/api/tools")
async def list_tools():
    """列出所有可用工具"""
    return {
        "total": len(TOOL_DESCRIPTIONS),
        "tools": [{"name": name, "display": display} for name, display in TOOL_DESCRIPTIONS.items()],
    }


# 设备类型 -> 温度字段映射
TEMP_FIELD_MAP = {
    "CNC": "spindle_temp",
    "INJECTION": "mold_temp",
    "PRESS": "motor_temp",
    "STAMPING": "motor_temp",
    "ASSEMBLY": "temperature",
}


@app.get("/api/equipment/status")
async def get_equipment_status():
    """获取设备状态列表（供前端监控面板使用）"""
    data_dir = DATA_DIR
    try:
        with open(data_dir / "equipment_status.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="设备数据文件不存在")

    devices = []
    for eq_id, eq in raw.items():
        eq_type = eq.get("type", "")
        temp_field = TEMP_FIELD_MAP.get(eq_type, "temperature")
        latest = eq.get("latest", {})
        devices.append({
            "id": eq_id,
            "name": eq.get("name", eq_id),
            "type": eq_type,
            "line": eq.get("line", ""),
            "status": eq.get("status", "未知"),
            "temperature": latest.get(temp_field, 0),
            "temperature_field": temp_field,
            "power": latest.get("power", 0),
        })

    return {"total": len(devices), "devices": devices}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
