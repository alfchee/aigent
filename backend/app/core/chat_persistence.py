from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from app.core.paths import workspace_db_dir


@dataclass
class ChatPersistenceConfig:
    db_path: str = str((workspace_db_dir() / "chat_messages.db").as_posix())


class ChatPersistence:
    def __init__(self, config: Optional[ChatPersistenceConfig] = None):
        self.config = config or ChatPersistenceConfig()
        self.db_file = Path(self.config.db_path)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._ensure_history_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    meta_json TEXT,
                    inserted_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                ON chat_messages(session_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_conversation_created
                ON chat_messages(session_id, conversation_id, created_at DESC)
                """
            )
            conn.commit()

    def save_message(
        self,
        message_id: str,
        session_id: str,
        conversation_id: str,
        role: str,
        text: str,
        created_at: int,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                INSERT INTO chat_messages(id, session_id, conversation_id, role, text, created_at, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    session_id=excluded.session_id,
                    conversation_id=excluded.conversation_id,
                    role=excluded.role,
                    text=excluded.text,
                    created_at=excluded.created_at,
                    meta_json=excluded.meta_json
                """,
                (message_id, session_id, conversation_id, role, text, created_at, meta_json),
            )
            conn.commit()

    def list_messages(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
        before_created_at: Optional[int] = None,
        limit: int = 50,
    ) -> list[dict]:
        safe_limit = max(1, min(limit, 200))
        query = """
            SELECT id, session_id, conversation_id, role, text, created_at, meta_json
            FROM chat_messages
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]
        if conversation_id is not None:
            query += " AND conversation_id = ?"
            params.append(conversation_id)
        if before_created_at is not None:
            query += " AND created_at < ?"
            params.append(before_created_at)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(safe_limit)
        with sqlite3.connect(self.db_file) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        rows = list(reversed(rows))
        out = []
        for row in rows:
            meta_json = row[6] or "{}"
            try:
                meta = json.loads(meta_json)
            except Exception:
                meta = {}
            out.append(
                {
                    "id": row[0],
                    "session_id": row[1],
                    "conversation_id": row[2],
                    "role": row[3],
                    "text": row[4],
                    "created_at": row[5],
                    "meta": meta,
                }
            )
        return out

    # ------------------------------------------------------------------
    # Agent session history — stores full LangGraph BaseMessage lists
    # ------------------------------------------------------------------

    def _ensure_history_schema(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_session_history (
                    session_id TEXT NOT NULL,
                    position   INTEGER NOT NULL,
                    msg_type   TEXT NOT NULL,
                    content    TEXT NOT NULL DEFAULT '',
                    extra_json TEXT NOT NULL DEFAULT '{}',
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                    PRIMARY KEY (session_id, position)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_history_session
                ON agent_session_history(session_id)
                """
            )
            conn.commit()

    def load_history(self, session_id: str) -> List[Any]:
        """Return the persisted BaseMessage list for *session_id*, or [] if none."""
        from langchain_core.messages import (
            AIMessage,
            FunctionMessage,
            HumanMessage,
            ToolMessage,
        )

        with sqlite3.connect(self.db_file) as conn:
            rows = conn.execute(
                """
                SELECT msg_type, content, extra_json
                FROM agent_session_history
                WHERE session_id = ?
                ORDER BY position ASC
                """,
                (session_id,),
            ).fetchall()

        messages: List[Any] = []
        for msg_type, content, extra_json in rows:
            try:
                extra: dict = json.loads(extra_json or "{}")
            except Exception:
                extra = {}

            if msg_type == "human":
                messages.append(HumanMessage(content=content))
            elif msg_type == "ai":
                msg = AIMessage(content=content)
                if extra.get("tool_calls"):
                    msg.tool_calls = extra["tool_calls"]
                messages.append(msg)
            elif msg_type == "tool":
                messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=extra.get("tool_call_id", ""),
                        name=extra.get("name", ""),
                    )
                )
            elif msg_type == "function":
                messages.append(
                    FunctionMessage(
                        content=content,
                        name=extra.get("name", ""),
                    )
                )
        return messages

    def save_history(self, session_id: str, messages: List[Any]) -> None:
        """Replace the persisted history for *session_id* with *messages*."""
        from langchain_core.messages import (
            AIMessage,
            FunctionMessage,
            HumanMessage,
            ToolMessage,
        )

        now = int(time.time())
        rows = []
        for position, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                rows.append((session_id, position, "human", msg.content or "{}", "{}", now))
            elif isinstance(msg, AIMessage):
                extra: dict = {}
                tool_calls = getattr(msg, "tool_calls", None) or []
                if tool_calls:
                    extra["tool_calls"] = tool_calls
                rows.append(
                    (
                        session_id,
                        position,
                        "ai",
                        msg.content or "",
                        json.dumps(extra, ensure_ascii=False),
                        now,
                    )
                )
            elif isinstance(msg, ToolMessage):
                extra = {
                    "tool_call_id": getattr(msg, "tool_call_id", "") or "",
                    "name": getattr(msg, "name", "") or "",
                }
                rows.append(
                    (
                        session_id,
                        position,
                        "tool",
                        msg.content or "",
                        json.dumps(extra, ensure_ascii=False),
                        now,
                    )
                )
            elif isinstance(msg, FunctionMessage):
                extra = {"name": getattr(msg, "name", "") or ""}
                rows.append(
                    (
                        session_id,
                        position,
                        "function",
                        msg.content or "",
                        json.dumps(extra, ensure_ascii=False),
                        now,
                    )
                )

        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "DELETE FROM agent_session_history WHERE session_id = ?",
                (session_id,),
            )
            if rows:
                conn.executemany(
                    """
                    INSERT INTO agent_session_history
                        (session_id, position, msg_type, content, extra_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            conn.commit()
