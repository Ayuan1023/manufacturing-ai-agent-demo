"""
Agent 状态定义
"""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 运行状态"""
    # 对话消息历史
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # 待确认的写操作（HITL）
    pending_confirmation: dict | None
    # 工具调用记录（用于前端展示）
    tool_calls_log: list[dict]
