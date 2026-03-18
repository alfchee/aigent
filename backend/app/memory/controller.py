from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.paths import workspace_db_dir
from app.memory.episodic import EpisodicMemory, EpisodicMemoryConfig
from app.memory.semantic import SemanticMemory, SemanticMemoryConfig


@dataclass
class MemoryControllerConfig:
    user_id: str
    episodic_db_path: str = str((workspace_db_dir() / "episodic_memory.db").as_posix())


class MemoryController:
    def __init__(self, user_id: str, config: Optional[MemoryControllerConfig] = None):
        cfg = config or MemoryControllerConfig(user_id=user_id)
        self.user_id = user_id
        self.semantic = SemanticMemory(SemanticMemoryConfig(user_id=user_id))
        self.episodic = EpisodicMemory(EpisodicMemoryConfig(db_path=cfg.episodic_db_path))

    def add_fact(self, content: str, path: str = "facts/general.md") -> None:
        _ = path
        self.semantic.add(content)

    def retrieve_context(self, query: str) -> str:
        items = self.semantic.search(query, top_k=5)
        if not items:
            return ""
        body = "\n".join(f"- {item}" for item in items)
        return f"Relevant Context:\n{body}"

    def save_session_summary(self, session_id: str, summary: str) -> None:
        self.episodic.append_summary(session_id, summary)

    def get_latest_summary(self, session_id: str) -> Optional[str]:
        return self.episodic.get_latest_summary(session_id)

    def get_summaries_since(self, session_id: str, since_ts: int, limit: int = 20) -> list[dict]:
        return self.episodic.list_summaries(session_id=session_id, since_ts=since_ts, limit=limit)
