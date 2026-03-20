from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("navibot.cost_monitor")

GEMINI_COST_PER_1M_INPUT_TOKENS = 0.125
GEMINI_COST_PER_1M_OUTPUT_TOKENS = 0.375

GPT4O_COST_PER_1M_INPUT_TOKENS = 2.5
GPT4O_COST_PER_1M_OUTPUT_TOKENS = 10.0


@dataclass
class LLMCallRecord:
    timestamp: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    session_id: str
    cached: bool = False


@dataclass
class SessionCostSummary:
    session_id: str
    user_id: str
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls: List[LLMCallRecord] = field(default_factory=list)
    daily_limit_usd: float = 10.0
    created_at: str = ""
    last_call_at: str = ""

    def remaining_budget(self) -> float:
        return max(0.0, self.daily_limit_usd - self.total_cost_usd)

    def budget_exceeded(self) -> bool:
        return self.total_cost_usd >= self.daily_limit_usd

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "daily_limit_usd": self.daily_limit_usd,
            "remaining_budget_usd": round(self.remaining_budget(), 6),
            "budget_exceeded": self.budget_exceeded(),
            "last_call_at": self.last_call_at,
        }


class CostMonitor:
    _instance: Optional[CostMonitor] = None

    def __init__(self):
        self._sessions: Dict[str, SessionCostSummary] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._provider_costs: Dict[str, Dict[str, float]] = {
            "gemini": {
                "input_per_1m": GEMINI_COST_PER_1M_INPUT_TOKENS,
                "output_per_1m": GEMINI_COST_PER_1M_OUTPUT_TOKENS,
            },
            "openai": {
                "input_per_1m": GPT4O_COST_PER_1M_INPUT_TOKENS,
                "output_per_1m": GPT4O_COST_PER_1M_OUTPUT_TOKENS,
            },
            "anthropic": {
                "input_per_1m": 3.0,
                "output_per_1m": 15.0,
            },
        }

    @classmethod
    def get_instance(cls) -> CostMonitor:
        if cls._instance is None:
            with threading.Lock():
                if cls._instance is None:
                    cls._instance = CostMonitor()
        return cls._instance

    def _get_or_create_session(self, session_id: str, user_id: str) -> SessionCostSummary:
        with self._global_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionCostSummary(
                    session_id=session_id,
                    user_id=user_id,
                    created_at=datetime.now().isoformat(),
                )
                self._session_locks[session_id] = threading.Lock()
            return self._sessions[session_id]

    def _compute_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        provider_key = provider.lower()
        if provider_key not in self._provider_costs:
            provider_key = "openai"
        rates = self._provider_costs[provider_key]
        input_cost = (input_tokens / 1_000_000) * rates["input_per_1m"]
        output_cost = (output_tokens / 1_000_000) * rates["output_per_1m"]
        return input_cost + output_cost

    def record_call(
        self,
        session_id: str,
        user_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
    ) -> LLMCallRecord:
        summary = self._get_or_create_session(session_id, user_id)
        with self._session_locks.get(session_id, self._global_lock):
            cost = self._compute_cost(provider, model, input_tokens, output_tokens)
            if cached:
                cost = 0.0
            record = LLMCallRecord(
                timestamp=datetime.now().isoformat(),
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                session_id=session_id,
                cached=cached,
            )
            summary.total_calls += 1
            summary.total_input_tokens += input_tokens
            summary.total_output_tokens += output_tokens
            summary.total_cost_usd += cost
            summary.last_call_at = record.timestamp
            summary.calls.append(record)
            return record

    def get_session_summary(self, session_id: str) -> Optional[SessionCostSummary]:
        with self._global_lock:
            return self._sessions.get(session_id)

    def get_all_summaries(self) -> List[Dict]:
        with self._global_lock:
            return [s.to_dict() for s in self._sessions.values()]

    def get_total_cost(self) -> float:
        with self._global_lock:
            return sum(s.total_cost_usd for s in self._sessions.values())

    def reset_session(self, session_id: str) -> None:
        with self._global_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._session_locks:
                del self._session_locks[session_id]

    def set_daily_limit(self, session_id: str, limit_usd: float) -> None:
        summary = self._get_or_create_session(session_id, "default")
        with self._session_locks.get(session_id, self._global_lock):
            summary.daily_limit_usd = limit_usd


_cost_monitor_instance = CostMonitor.get_instance()


def get_cost_monitor() -> CostMonitor:
    return _cost_monitor_instance
