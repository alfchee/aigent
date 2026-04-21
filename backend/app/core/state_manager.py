from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("navibot.state_manager")


@dataclass
class WorkerStatus:
    role_id: str
    name: str
    current_task: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "idle"


@dataclass
class BudgetInfo:
    daily_limit: float = 100.0
    spent_today: float = 0.0
    currency: str = "USD"
    last_reset: str = ""


@dataclass
class TaskRecord:
    task_id: str
    description: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None


@dataclass
class GlobalState:
    session_id: str
    user_id: str
    last_activity: str = ""
    active_worker: Optional[str] = None
    workers: Dict[str, WorkerStatus] = field(default_factory=dict)
    budget: BudgetInfo = field(default_factory=BudgetInfo)
    completed_tasks: List[TaskRecord] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    last_tool_used: Optional[str] = None
    last_tool_result: Optional[str] = None
    total_turns: int = 0
    total_errors: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_dashboard_summary(self) -> str:
        lines = [
            f"Session: {self.session_id}",
            f"User: {self.user_id}",
            f"Last Activity: {self.last_activity}",
            f"Turns: {self.total_turns} | Errors: {self.total_errors}",
        ]
        if self.active_worker:
            lines.append(f"Active Worker: {self.active_worker}")
        if self.budget.spent_today > 0:
            lines.append(f"Budget: ${self.budget.spent_today:.2f}/{self.budget.daily_limit:.2f} {self.budget.currency}")
        if self.completed_tasks:
            lines.append(f"Completed Tasks: {len(self.completed_tasks)}")
        if self.pending_tasks:
            lines.append(f"Pending: {len(self.pending_tasks)}")
        return "\n".join(lines)


class GlobalStateManager:
    _instance: Optional[GlobalStateManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self._sessions: Dict[str, GlobalState] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> GlobalStateManager:
        if cls._instance is None:
            with threading.Lock():
                if cls._instance is None:
                    cls._instance = GlobalStateManager()
        return cls._instance

    def get_session_state(self, session_id: str, user_id: str = "default_user") -> GlobalState:
        with self._global_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = GlobalState(
                    session_id=session_id,
                    user_id=user_id,
                    last_activity=datetime.now().isoformat(),
                    budget=BudgetInfo(last_reset=datetime.now().strftime("%Y-%m-%d")),
                )
                self._session_locks[session_id] = threading.Lock()
            return self._sessions[session_id]

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        with self._global_lock:
            return self._session_locks.get(session_id, self._global_lock)

    def update_activity(self, session_id: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.last_activity = datetime.now().isoformat()
            state.total_turns += 1

    def set_active_worker(self, session_id: str, worker_id: Optional[str], task: Optional[str] = None) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.active_worker = worker_id
            if worker_id and worker_id.startswith("worker_"):
                role_id = worker_id.replace("worker_", "")
                if role_id not in state.workers:
                    state.workers[role_id] = WorkerStatus(role_id=role_id, name=role_id)
                state.workers[role_id].current_task = task
                state.workers[role_id].status = "working"

    def complete_worker_task(self, session_id: str, worker_id: str, result_summary: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            # Normalise key the same way set_active_worker() does
            role_id = worker_id.replace("worker_", "", 1) if worker_id.startswith("worker_") else worker_id
            w: Optional[WorkerStatus] = state.workers.get(role_id)
            now = datetime.now().isoformat()
            if w is not None:
                w.status = "idle"
                w.current_task = None
                w.completed_at = now
            state.completed_tasks.append(TaskRecord(
                task_id=f"task_{len(state.completed_tasks) + 1}",
                description=w.name if w is not None else role_id,
                status="completed",
                started_at=(w.completed_at if w is not None else None) or now,
                completed_at=now,
                result_summary=result_summary[:200] if result_summary else None,
            ))
            state.active_worker = None

    def add_pending_task(self, session_id: str, task_description: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.pending_tasks.append(task_description)

    def complete_pending_task(self, session_id: str, task_description: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            if task_description in state.pending_tasks:
                state.pending_tasks.remove(task_description)

    def record_tool_use(self, session_id: str, tool_name: str, result: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.last_tool_used = tool_name
            state.last_tool_result = result[:500] if result else ""

    def record_error(self, session_id: str) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.total_errors += 1

    def update_budget(self, session_id: str, amount: float) -> None:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            state.budget.spent_today += amount

    def get_state_json(self, session_id: str) -> str:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            return state.to_json()

    def get_dashboard(self, session_id: str) -> str:
        state = self.get_session_state(session_id)
        with self._get_session_lock(session_id):
            return state.get_dashboard_summary()


_state_manager = GlobalStateManager.get_instance()


def get_state_manager() -> GlobalStateManager:
    return _state_manager
