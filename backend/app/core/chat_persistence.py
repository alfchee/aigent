from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
