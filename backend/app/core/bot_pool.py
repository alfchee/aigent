from __future__ import annotations

import threading
from typing import Dict

from app.core.agent import NaviBot


class BotPool:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bots: Dict[str, NaviBot] = {}

    def get(self, model_name: str) -> NaviBot:
        name = (model_name or "").strip() or "gemini-flash-latest"
        with self._lock:
            bot = self._bots.get(name)
            if bot is not None:
                return bot
            bot = NaviBot(model_name=name)
            self._bots[name] = bot
            return bot


bot_pool = BotPool()
