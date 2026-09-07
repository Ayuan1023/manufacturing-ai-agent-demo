"""
会话管理：存储多轮对话的历史消息
支持并发锁、TTL 过期、定期清理
"""
import time
import threading
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage


class SessionManager:
    """会话管理器，基于内存存储，线程安全"""

    def __init__(self, max_history: int = 20, ttl_seconds: int = 3600):
        self._sessions: dict[str, dict] = {}
        self._max_history = max_history
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cleanup_counter = 0

    def get_or_create(self, session_id: str) -> dict:
        """获取或创建会话（线程安全）"""
        with self._lock:
            now = time.time()
            # 每100次访问触发一次过期清理
            self._cleanup_counter += 1
            if self._cleanup_counter >= 100:
                self._cleanup_expired_locked(now)
                self._cleanup_counter = 0

            if session_id in self._sessions:
                session = self._sessions[session_id]
                if now - session["last_active"] > self._ttl:
                    session = self._create_locked(session_id, now)
                else:
                    session["last_active"] = now
            else:
                session = self._create_locked(session_id, now)
            return session

    def _create_locked(self, session_id: str, now: float) -> dict:
        """创建新会话（调用方需持有锁）"""
        session = {
            "session_id": session_id,
            "history": [],
            "created_at": now,
            "last_active": now,
            "message_count": 0,
        }
        self._sessions[session_id] = session
        return session

    def _cleanup_expired_locked(self, now: float):
        """清理过期会话（调用方需持有锁）"""
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s["last_active"] > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]

    def add_messages(self, session_id: str, human_msg: str, ai_msg: str):
        """添加一轮对话到历史（线程安全）"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                now = time.time()
                session = self._create_locked(session_id, now)

            session["history"].append(HumanMessage(content=human_msg))
            session["history"].append(AIMessage(content=ai_msg))
            session["message_count"] += 1
            session["last_active"] = time.time()

            # 限制历史长度
            if len(session["history"]) > self._max_history * 2:
                session["history"] = session["history"][-self._max_history * 2:]

    def get_history(self, session_id: str) -> list:
        """获取会话历史"""
        session = self.get_or_create(session_id)
        return session["history"]

    def clear(self, session_id: str):
        """清空会话历史"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["history"] = []
                self._sessions[session_id]["message_count"] = 0

    def get_stats(self) -> dict:
        """获取会话统计"""
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "total_messages": sum(s["message_count"] for s in self._sessions.values()),
            }


# 全局单例
session_manager = SessionManager()
