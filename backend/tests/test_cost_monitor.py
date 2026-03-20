import pytest
import json
from app.core.cost_monitor import (
    CostMonitor,
    SessionCostSummary,
    get_cost_monitor,
)


class TestCostMonitor:
    def setup_method(self):
        self.monitor = CostMonitor()

    def test_record_call_computes_cost(self):
        record = self.monitor.record_call(
            session_id="s1",
            user_id="u1",
            provider="gemini",
            model="gemini-flash-lite",
            input_tokens=1000000,
            output_tokens=500000,
        )
        assert record.cost_usd > 0
        assert record.provider == "gemini"
        assert record.session_id == "s1"

    def test_record_call_cached_is_free(self):
        record = self.monitor.record_call(
            session_id="s1",
            user_id="u1",
            provider="gemini",
            model="gemini-flash-lite",
            input_tokens=1000000,
            output_tokens=500000,
            cached=True,
        )
        assert record.cost_usd == 0.0

    def test_get_session_summary(self):
        self.monitor.record_call("s1", "u1", "gemini", "model", 1000, 500)
        summary = self.monitor.get_session_summary("s1")
        assert summary is not None
        assert summary.session_id == "s1"
        assert summary.total_calls >= 1

    def test_get_session_summary_not_found(self):
        summary = self.monitor.get_session_summary("nonexistent")
        assert summary is None

    def test_get_all_summaries(self):
        self.monitor.record_call("s1", "u1", "gemini", "model", 100, 50)
        self.monitor.record_call("s2", "u2", "openai", "gpt-4o", 100, 50)
        summaries = self.monitor.get_all_summaries()
        assert len(summaries) >= 2

    def test_get_total_cost(self):
        self.monitor.record_call("s1", "u1", "gemini", "model", 1000000, 0)
        self.monitor.record_call("s2", "u1", "gemini", "model", 0, 1000000)
        total = self.monitor.get_total_cost()
        assert total > 0

    def test_reset_session(self):
        self.monitor.record_call("s1", "u1", "gemini", "model", 100, 50)
        self.monitor.reset_session("s1")
        assert self.monitor.get_session_summary("s1") is None

    def test_set_daily_limit(self):
        self.monitor.set_daily_limit("s1", 5.0)
        summary = self.monitor.get_session_summary("s1")
        assert summary.daily_limit_usd == 5.0

    def test_session_cost_summary_dict(self):
        self.monitor.record_call("s1", "u1", "gemini", "model", 100, 50)
        summary = self.monitor.get_session_summary("s1")
        d = summary.to_dict()
        assert "session_id" in d
        assert "total_cost_usd" in d
        assert "remaining_budget_usd" in d
        assert "budget_exceeded" in d

    def test_singleton(self):
        m1 = get_cost_monitor()
        m2 = get_cost_monitor()
        assert m1 is m2
