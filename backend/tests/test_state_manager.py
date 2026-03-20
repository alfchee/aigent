import pytest
import json
from app.core.state_manager import (
    GlobalStateManager,
    GlobalState,
    WorkerStatus,
    BudgetInfo,
    get_state_manager,
)


class TestGlobalState:
    def test_to_json(self):
        state = GlobalState(session_id="s1", user_id="u1")
        json_str = state.to_json()
        parsed = json.loads(json_str)
        assert parsed["session_id"] == "s1"
        assert parsed["user_id"] == "u1"

    def test_to_dict(self):
        state = GlobalState(session_id="s1", user_id="u1")
        d = state.to_dict()
        assert d["session_id"] == "s1"

    def test_get_dashboard_summary(self):
        state = GlobalState(session_id="s1", user_id="u1", total_turns=5)
        dashboard = state.get_dashboard_summary()
        assert "s1" in dashboard
        assert "5" in dashboard


class TestGlobalStateManager:
    def setup_method(self):
        self.mgr = GlobalStateManager()

    def test_get_session_state_creates_if_missing(self):
        state = self.mgr.get_session_state("new_session", "user1")
        assert state.session_id == "new_session"
        assert state.user_id == "user1"

    def test_get_session_state_returns_existing(self):
        s1 = self.mgr.get_session_state("s1", "u1")
        s2 = self.mgr.get_session_state("s1", "u1")
        assert s1 is s2

    def test_update_activity_increments_turns(self):
        state = self.mgr.get_session_state("s1", "u1")
        assert state.total_turns == 0
        self.mgr.update_activity("s1")
        assert state.total_turns == 1
        self.mgr.update_activity("s1")
        assert state.total_turns == 2

    def test_record_tool_use(self):
        self.mgr.record_tool_use("s1", "web_browse", "Found 10 results")
        state = self.mgr.get_session_state("s1")
        assert state.last_tool_used == "web_browse"
        assert "Found 10" in state.last_tool_result

    def test_record_error(self):
        self.mgr.record_error("s1")
        state = self.mgr.get_session_state("s1")
        assert state.total_errors == 1

    def test_update_budget(self):
        self.mgr.update_budget("s1", 0.05)
        state = self.mgr.get_session_state("s1")
        assert state.budget.spent_today == 0.05

    def test_get_state_json(self):
        json_str = self.mgr.get_state_json("s1")
        parsed = json.loads(json_str)
        assert "session_id" in parsed

    def test_singleton(self):
        m1 = get_state_manager()
        m2 = get_state_manager()
        assert m1 is m2
