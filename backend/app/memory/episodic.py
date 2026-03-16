from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class EpisodicMemoryConfig:
    db_path: str = "workspace/db/episodic_memory.db"


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
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            conn.commit()

    def save_summary(self, session_id: str, summary: str) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """
                INSERT INTO session_summaries(session_id, summary, updated_at)
                VALUES (?, ?, strftime('%s','now'))
                ON CONFLICT(session_id)
                DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at
                """,
                (session_id, summary),
            )
            conn.commit()

    def get_summary(self, session_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_file) as conn:
            row = conn.execute(
                "SELECT summary FROM session_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row[0] if row else None
