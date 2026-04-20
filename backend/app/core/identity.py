import os
import logging
from pathlib import Path
from app.core.paths import workspace_config_dir

logger = logging.getLogger("navibot.identity")

SOUL_FILE = workspace_config_dir() / "soul_prompt.txt"

DEFAULT_SOUL = """You are NaviBot Supervisor, an intelligent orchestrator.
Your primary directive is to be helpful, direct, and concise.
You manage the conversation and delegate specialized tasks to the appropriate workers.
When responding directly, do not use unnecessary filler words.
"""

class IdentityManager:
    def __init__(self):
        self._ensure_config_dir()
        self._soul_cache = None

    def _ensure_config_dir(self):
        workspace_config_dir().mkdir(parents=True, exist_ok=True)
        if not SOUL_FILE.exists():
            self.update_soul(DEFAULT_SOUL)

    def get_soul(self) -> str:
        """Read and return the soul prompt."""
        if self._soul_cache is not None:
            return self._soul_cache
            
        try:
            if SOUL_FILE.exists():
                content = SOUL_FILE.read_text(encoding="utf-8")
                self._soul_cache = content
                return content
            return DEFAULT_SOUL
        except Exception as e:
            logger.error("Failed to read soul prompt from %s: %s", SOUL_FILE, e)
            return DEFAULT_SOUL

    def update_soul(self, new_soul: str) -> None:
        """Update the soul prompt and save to file."""
        try:
            SOUL_FILE.write_text(new_soul.strip(), encoding="utf-8")
            self._soul_cache = new_soul.strip()
            logger.info("Soul prompt updated successfully")
        except Exception as e:
            logger.error("Failed to write soul prompt to %s: %s", SOUL_FILE, e)
            raise e

_identity_manager_instance = None

def get_identity_manager() -> IdentityManager:
    global _identity_manager_instance
    if _identity_manager_instance is None:
        _identity_manager_instance = IdentityManager()
    return _identity_manager_instance
