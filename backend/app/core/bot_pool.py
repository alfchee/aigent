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

    async def reload_all_mcp(self):
        """Reloads MCP configuration for all active bots."""
        # We need a snapshot of bots to avoid lock issues during async ops
        with self._lock:
            bots = list(self._bots.values())
        
        for bot in bots:
            try:
                await bot.reload_mcp()
            except Exception as e:
                print(f"Error reloading MCP for bot {bot.model_name}: {e}")

    async def close_all(self):
        """Closes all bots and releases resources."""
        with self._lock:
            bots = list(self._bots.values())
            self._bots.clear()
        
        for bot in bots:
            try:
                await bot.close()
            except Exception as e:
                print(f"Error closing bot {bot.model_name}: {e}")


bot_pool = BotPool()
