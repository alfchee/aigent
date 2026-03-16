from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.memory.openviking_store import MemoryController as OpenVikingMemoryController


@dataclass
class SemanticMemoryConfig:
    user_id: str = "default_user"
    qdrant_url: Optional[str] = None
    fallback_store: Dict[str, List[str]] = field(default_factory=dict)


class SemanticMemory:
    def __init__(self, config: Optional[SemanticMemoryConfig] = None):
        self.config = config or SemanticMemoryConfig()
        self._fallback = self.config.fallback_store
        self._ov: Optional[OpenVikingMemoryController] = None
        try:
            self._ov = OpenVikingMemoryController(user_id=self.config.user_id)
        except Exception:
            self._ov = None

    @property
    def memory(self) -> Optional[OpenVikingMemoryController]:
        return self._ov

    def add(self, text: str) -> None:
        if self._ov:
            self._ov.add_fact(text)
            return
        self._fallback.setdefault(self.config.user_id, []).append(text)

    def search(self, query: str, top_k: int = 5) -> List[str]:
        if self._ov:
            context = self._ov.retrieve_context(query).strip()
            if not context:
                return []
            lines = [line.strip("- ").strip() for line in context.splitlines() if line.strip() and not line.startswith("Relevant Context")]
            return lines[:top_k]
        values = self._fallback.get(self.config.user_id, [])
        ranked = [item for item in values if query.lower() in item.lower()]
        return ranked[:top_k] if ranked else values[:top_k]
