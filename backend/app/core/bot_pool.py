from __future__ import annotations

import asyncio
import threading
from typing import Dict, Optional

from app.core.agent import NaviBot


class BotPool:
    """
    Pool de bots que gestiona instancias de NaviBot.
    
    Ahora soporta integración con ToolRegistry para manejo unificado
    de herramientas.
    """
    
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
    
    async def initialize_tool_registry(self):
        """
        Inicializa el ToolRegistry global.
        
        Debe ser llamado al iniciar la aplicación.
        """
        try:
            from app.core.tool_registry import initialize_tool_registry
            registry = await initialize_tool_registry()
            return registry
        except Exception as e:
            print(f"Error initializing ToolRegistry: {e}")
            return None
    
    def get_tool_registry_status(self) -> Dict:
        """
        Obtiene el estado del ToolRegistry.
        
        Returns:
            Dict con el estado o None si no está inicializado
        """
        try:
            from app.core.tool_registry import get_tool_registry
            registry = get_tool_registry()
            return registry.get_stats()
        except Exception as e:
            return {"error": str(e)}

    async def reload_all_mcp(self):
        """Recarga la configuración de MCP para todos los bots activos y el ToolRegistry."""
        # 1. Recargar ToolRegistry si está disponible
        try:
            from app.core.tool_registry import get_tool_registry
            registry = get_tool_registry()
            if registry:
                await registry.reload_mcp_tools()
                print("ToolRegistry MCP tools reloaded")
        except Exception as e:
            print(f"Error reloading ToolRegistry: {e}")
        
        # 2. Recargar MCPs en cada bot
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

    def clear(self):
        """Clears all bots from the pool, forcing re-initialization on next use."""
        with self._lock:
            self._bots.clear()



bot_pool = BotPool()
