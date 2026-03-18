from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from app.core.paths import workspace_db_dir


@dataclass
class EpisodicMemoryConfig:
    db_path: str = str((workspace_db_dir() / "episodic_memory.db").as_posix())


class EpisodicMemory:
    def __init__(self, config: Optional[EpisodicMemoryConfig] = None):
        self.config = config or EpisodicMemoryConfig()
        self.db_file = Path(self.config.db_path)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_summaries_session_updated
                ON session_summaries(session_id, updated_at DESC)
                """
            )
            conn.commit()

    def save_summary(self, session_id: str, summary: str) -> None:
        self.append_summary(session_id, summary)

    def append_summary(self, session_id: str, summary: str) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                INSERT INTO session_summaries(session_id, summary, updated_at)
                VALUES (?, ?, strftime('%s','now'))
                """,
                (session_id, summary),
            )
            conn.commit()

    def get_summary(self, session_id: str) -> Optional[str]:
        return self.get_latest_summary(session_id)

    def get_latest_summary(self, session_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_file) as conn:
            row = conn.execute(
                """
                SELECT summary
                FROM session_summaries
                WHERE session_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return row[0] if row else None

    def list_summaries(self, session_id: str, since_ts: Optional[int] = None, limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(limit, 200))
        query = """
            SELECT id, session_id, summary, updated_at
            FROM session_summaries
            WHERE session_id = ?
        """
        params: list = [session_id]
        if since_ts is not None:
            query += " AND updated_at >= ?"
            params.append(since_ts)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(safe_limit)
        with sqlite3.connect(self.db_file) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            {"id": row[0], "session_id": row[1], "summary": row[2], "updated_at": row[3]}
            for row in rows
        ]
