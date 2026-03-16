import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

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

class RoleManager:
    """
    Manages loading and retrieval of agent roles from JSON config.
    """
    def __init__(self, config_path: str = "workspace/config/roles.json"):
        self.config_path = config_path
        self.supervisor: Optional[SupervisorConfig] = None
        self.workers: List[AgentRole] = []
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            
            sup_data = data.get("supervisor", {})
            self.supervisor = SupervisorConfig(**sup_data)
            
            self.workers = [
                AgentRole(**w) for w in data.get("workers", [])
            ]
            logger.info(f"Loaded Supervisor and {len(self.workers)} Workers from config.")
        except Exception as e:
            logger.error(f"Failed to load roles config: {e}")
            # Fallback defaults
            self.supervisor = SupervisorConfig(
                name="Fallback Supervisor",
                description="Default supervisor",
                system_prompt="You are a helpful assistant."
            )

    def get_worker(self, role_id: str) -> Optional[AgentRole]:
        for w in self.workers:
            if w.role_id == role_id:
                return w
        return None

    def get_all_workers(self) -> List[AgentRole]:
        return self.workers

# Singleton
role_manager = RoleManager()
