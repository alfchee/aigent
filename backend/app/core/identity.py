import os
import logging
from pathlib import Path
from app.core.paths import workspace_config_dir

logger = logging.getLogger("navibot.identity")

DEFAULT_SOUL = """You are NaviBot Supervisor, an intelligent orchestrator.
Your primary directive is to be helpful, direct, and concise.
You manage the conversation and delegate specialized tasks to the appropriate workers.
When responding directly, do not use unnecessary filler words.
"""

class IdentityManager:
    def __init__(self):
        # Compute the path at construction time so monkeypatching workspace_config_dir
        # before instantiation takes effect (avoids module-level constant pitfall).
        self._soul_file: Path = workspace_config_dir() / "soul_prompt.txt"
        self._soul_cache = None
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        self._soul_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._soul_file.exists():
            self.update_soul(DEFAULT_SOUL)

    def get_soul(self) -> str:
        """Read and return the soul prompt."""
        if self._soul_cache is not None:
            return self._soul_cache
            
        try:
            if self._soul_file.exists():
                content = self._soul_file.read_text(encoding="utf-8")
                self._soul_cache = content
                return content
            return DEFAULT_SOUL
        except Exception as e:
            logger.error("Failed to read soul prompt from %s: %s", self._soul_file, e)
            return DEFAULT_SOUL

    def update_soul(self, new_soul: str) -> None:
        """Update the soul prompt and save to file."""
        try:
            self._soul_file.write_text(new_soul.strip(), encoding="utf-8")
            self._soul_cache = new_soul.strip()
            logger.info("Soul prompt updated successfully")
        except Exception as e:
            logger.error("Failed to write soul prompt to %s: %s", self._soul_file, e)
            raise e

_identity_manager_instance = None

def get_identity_manager() -> IdentityManager:
    global _identity_manager_instance
    if _identity_manager_instance is None:
        _identity_manager_instance = IdentityManager()
    return _identity_manager_instance
