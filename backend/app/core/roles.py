import json
import logging
import os
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
    system_prompt: str
    skills: List[str] = Field(default_factory=list)

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
        return worker.model_copy(update={"skills": normalized_skills})

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

# Singleton
role_manager = RoleManager()
