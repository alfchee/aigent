import json
import logging
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.paths import workspace_config_dir

logger = logging.getLogger("navibot.core.roles")

class AgentRole(BaseModel):
    role_id: str
    name: str
    description: str
    model: str = "gpt-4o"
    provider_override: Optional[str] = None
    system_prompt: str
    skills: List[str] = Field(default_factory=list)
    mcp_servers: List[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SupervisorConfig(BaseModel):
    name: str
    description: str
    model: str = "gpt-4o"
    system_prompt: str

class RolesSnapshot(BaseModel):
    config_path: str
    updated_at: float
    supervisor: SupervisorConfig
    workers: List[AgentRole]

class RoleManager:
    def __init__(self, config_path: str = str((workspace_config_dir() / "roles.json").as_posix())):
        self.config_path = os.path.abspath(config_path)
        self.supervisor: Optional[SupervisorConfig] = None
        self.workers: List[AgentRole] = []
        self.updated_at: float = 0.0
        self._lock = Lock()
        self._load_config()

    def _normalize_worker(self, worker: AgentRole) -> AgentRole:
        normalized_skills = sorted({skill.strip() for skill in worker.skills if skill and skill.strip()})
        normalized_mcp = sorted({s.strip() for s in worker.mcp_servers if s and s.strip()})
        return worker.model_copy(update={"skills": normalized_skills, "mcp_servers": normalized_mcp})

    def _load_config(self) -> None:
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            sup_data = data.get("supervisor", {})
            supervisor = SupervisorConfig(**sup_data)
            workers = [self._normalize_worker(AgentRole(**w)) for w in data.get("workers", [])]
            with self._lock:
                self.supervisor = supervisor
                self.workers = workers
                self.updated_at = os.path.getmtime(self.config_path)
            logger.info("Loaded Supervisor and %s Workers from config.", len(workers))
        except Exception as e:
            logger.error(f"Failed to load roles config: {e}")
            fallback = SupervisorConfig(name="Fallback Supervisor", description="Default supervisor", system_prompt="You are a helpful assistant.")
            with self._lock:
                self.supervisor = fallback
                self.workers = []
                self.updated_at = 0.0

    def reload(self) -> RolesSnapshot:
        self._load_config()
        return self.snapshot()

    def _serialize_config(self) -> None:
        """Write current in-memory state back to roles.json."""
        with self._lock:
            sup_data = self.supervisor.model_dump() if self.supervisor else {}
            workers_data = [w.model_dump(mode="json") for w in self.workers]
        data = {"supervisor": sup_data, "workers": workers_data}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Serialized %d workers to %s", len(workers_data), self.config_path)

    def snapshot(self) -> RolesSnapshot:
        with self._lock:
            supervisor = self.supervisor or SupervisorConfig(
                name="Fallback Supervisor",
                description="Default supervisor",
                system_prompt="You are a helpful assistant.",
            )
            workers = [worker.model_copy() for worker in self.workers]
            return RolesSnapshot(
                config_path=self.config_path,
                updated_at=self.updated_at,
                supervisor=supervisor,
                workers=workers,
            )

    def role_for_skill(self, skill_name: str) -> Optional[AgentRole]:
        with self._lock:
            for worker in self.workers:
                if skill_name in worker.skills:
                    return worker
        return None

    def get_worker(self, role_id: str) -> Optional[AgentRole]:
        with self._lock:
            for w in self.workers:
                if w.role_id == role_id:
                    return w
        return None

    def get_all_workers(self) -> List[AgentRole]:
        with self._lock:
            return [worker.model_copy() for worker in self.workers]

    # --- Write-back methods ---

    def get_role(self, role_id: str) -> AgentRole:
        """Returns a single role by ID. Raises KeyError if not found."""
        role = self.get_worker(role_id)
        if role is None:
            raise KeyError(f"Role '{role_id}' not found.")
        return role

    def create_role(self, role: AgentRole) -> AgentRole:
        """Adds role to in-memory list, serializes roles.json, triggers reload."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for w in self.workers:
                if w.role_id == role.role_id:
                    raise ValueError(f"Role '{role.role_id}' already exists.")
            normalized = self._normalize_worker(
                role.model_copy(update={"created_at": now, "updated_at": now})
            )
            self.workers.append(normalized)
        self._serialize_config()
        self.reload()
        return self.get_role(role.role_id)

    def update_role(self, role_id: str, updates: dict) -> AgentRole:
        """Merges updates into matching role, serializes, triggers reload."""
        safe_updates = {k: v for k, v in updates.items() if k not in ("role_id", "created_at")}
        safe_updates["updated_at"] = datetime.now(timezone.utc)
        with self._lock:
            for i, w in enumerate(self.workers):
                if w.role_id == role_id:
                    self.workers[i] = self._normalize_worker(w.model_copy(update=safe_updates))
                    break
            else:
                raise KeyError(f"Role '{role_id}' not found.")
        self._serialize_config()
        self.reload()
        return self.get_role(role_id)

    def delete_role(self, role_id: str) -> None:
        """Removes role, serializes, triggers reload. Raises KeyError if not found."""
        with self._lock:
            for i, w in enumerate(self.workers):
                if w.role_id == role_id:
                    del self.workers[i]
                    break
            else:
                raise KeyError(f"Role '{role_id}' not found.")
        self._serialize_config()
        self.reload()

# Singleton
role_manager = RoleManager()
