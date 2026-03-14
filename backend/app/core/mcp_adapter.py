"""
McpAdapter - Adaptador de herramientas MCP para ToolRegistry

Este módulo integra el McpManager existente con el nuevo ToolRegistry,
proporcionando un bridge entre el sistema MCP y la arquitectura unificada.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import StructuredTool, BaseTool

from app.core.tool_registry import ToolRegistry, ToolMetadata

logger = logging.getLogger(__name__)


class McpAdapter:
    """
    Adaptador que conecta el McpManager existente con ToolRegistry.
    
    Proporciona:
    - Descubrimiento de herramientas desde servidores MCP activos
    - Conversión de herramientas MCP a formato LangChain
    - Health check de servidores MCP
    - Integración con el registry unificado
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        from app.core.mcp_client import McpManager
        from app.core.mcp_config import get_active_config_runtime
        
        self.registry = registry
        self.mcp_manager = McpManager()
        self._get_config = get_active_config_runtime
        self._servers_cache: Dict[str, Dict[str, Any]] = {}
        self._tools_cache: Optional[List[BaseTool]] = None
        self._cache_lock = asyncio.Lock()
        self._initialized = False
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Inicializa el adaptador y carga las herramientas MCP."""
        await self.mcp_manager.load_servers()
        await self.discover_and_register_tools()
    
    async def discover_and_register_tools(self) -> List[BaseTool]:
        """
        Descubre herramientas de todos los servidores MCP activos
        y las registra en el ToolRegistry.
        
        Returns:
            Lista de herramientas descubiertas
        """
        async with self._cache_lock:
            # Obtener herramientas de todos los servidores
            mcp_tools = await self.mcp_manager.get_all_tools()
            
            if not mcp_tools:
                self.logger.warning("No MCP tools discovered")
                return []
            
            tools = []
            
            for tool_def in mcp_tools:
                try:
                    # Convertir definición MCP a StructuredTool de LangChain
                    tool = await self._convert_mcp_to_tool(tool_def)
                    
                    if tool:
                        tools.append(tool)
                        
                        # Registrar en registry si existe
                        if self.registry:
                            # Determinar categoría basada en el servidor
                            server_id = tool_def.get("origin_session")
                            # Extraer nombre del servidor del tool name
                            tool_name = tool_def.get("name", "")
                            server_name = self._extract_server_name(tool_name)
                            
                            metadata = ToolMetadata(
                                name=tool.name,
                                source="mcp",
                                server=server_name,
                                category=self._infer_category_from_server(server_name),
                                description=tool.description or "",
                            )
                            
                            await self.registry.register_tool(tool, metadata)
                            
                except Exception as e:
                    self.logger.error(f"Error converting MCP tool {tool_def.get('name')}: {e}")
            
            self._tools_cache = tools
            self.logger.info(f"Registered {len(tools)} MCP tools")
            
            return tools
    
    async def _convert_mcp_to_tool(self, tool_def: Dict[str, Any]) -> Optional[BaseTool]:
        """
        Convierte una definición de herramienta MCP a StructuredTool de LangChain.
        
        Args:
            tool_def: Definición de herramienta desde MCP
            
        Returns:
            StructuredTool o None si falla la conversión
        """
        name = tool_def.get("name")
        description = tool_def.get("description", "")
        schema = tool_def.get("inputSchema", {})
        
        if not name:
            return None
        
        # Obtener la sesión de origen para ejecutar la herramienta
        origin_session = tool_def.get("origin_session")
        
        # Crear wrapper async que ejecute via McpManager
        async def mcp_wrapper(**kwargs):
            return await self.mcp_manager.call_tool(name, kwargs)
        
        # Crear StructuredTool
        try:
            structured_tool = StructuredTool.from_function(
                coroutine=mcp_wrapper,
                name=name,
                description=description,
            )
            return structured_tool
        except Exception as e:
            self.logger.error(f"Failed to create StructuredTool for {name}: {e}")
            return None
    
    def _extract_server_name(self, tool_name: str) -> str:
        """Extrae el nombre del servidor del nombre de la herramienta."""
        # MCP tools tienen formato: server_toolname
        if "_" in tool_name:
            return tool_name.split("_", 1)[0]
        return "unknown"
    
    def _infer_category_from_server(self, server_name: str) -> str:
        """Infiere la categoría basada en el servidor MCP."""
        server_lower = server_name.lower()
        
        categories = {
            "github": "development",
            "postgres": "data",
            "filesystem": "files",
            "slack": "communication",
            "jira": "productivity",
        }
        
        return categories.get(server_lower, "utility")
    
    async def reload_servers(self) -> None:
        """Recarga los servidores MCP."""
        await self.mcp_manager.sync_servers()
        await self.discover_and_register_tools()
    
    async def health_check_server(self, server_id: str) -> bool:
        """
        Verifica si un servidor MCP específico está disponible.
        
        Args:
            server_id: ID del servidor
            
        Returns:
            True si el servidor está disponible
        """
        return server_id in self.mcp_manager.active_sessions
    
    async def health_check_all_servers(self) -> Dict[str, bool]:
        """
        Verifica todos los servidores MCP.
        
        Returns:
            Dict con el estado de cada servidor
        """
        result = {}
        
        for server_id in self.mcp_manager.active_sessions:
            result[server_id] = True
        
        # Obtener servidores configurados pero no activos
        try:
            config = self._get_config()
            servers = config.get("servers", {})
            
            for server_id, settings in servers.items():
                if server_id not in result:
                    result[server_id] = False  # Configurado pero no activo
                    
        except Exception as e:
            self.logger.error(f"Error getting MCP config: {e}")
        
        return result
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Ejecuta una herramienta MCP específica.
        
        Args:
            tool_name: Nombre de la herramienta
            args: Argumentos
            
        Returns:
            Resultado de la ejecución
        """
        return await self.mcp_manager.call_tool(tool_name, args)
    
    async def get_server_tools(self, server_id: str) -> List[BaseTool]:
        """
        Obtiene todas las herramientas de un servidor específico.
        
        Args:
            server_id: ID del servidor
            
        Returns:
            Lista de herramientas del servidor
        """
        if self._tools_cache is None:
            await self.discover_and_register_tools()
        
        if not self._tools_cache:
            return []
        
        return [
            tool for tool in self._tools_cache
            if server_id in tool.name
        ]
    
    async def cleanup(self) -> None:
        """Limpia los recursos del adaptador."""
        await self.mcp_manager.cleanup()
        self._tools_cache = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del adaptador."""
        return {
            "active_servers": len(self.mcp_manager.active_sessions),
            "cached_tools": len(self._tools_cache) if self._tools_cache else 0,
            "sessions": list(self.mcp_manager.active_sessions.keys()),
        }


# Singleton accessor
_mcp_adapter_instance: Optional[McpAdapter] = None
_mcp_adapter_lock = asyncio.Lock()


async def get_mcp_adapter(registry: Optional[ToolRegistry] = None) -> McpAdapter:
    """Obtiene la instancia singleton del McpAdapter."""
    global _mcp_adapter_instance
    
    async with _mcp_adapter_lock:
        if _mcp_adapter_instance is None:
            _mcp_adapter_instance = McpAdapter(registry)
            await _mcp_adapter_instance.initialize()
        
        return _mcp_adapter_instance


async def initialize_mcp_adapter(registry: ToolRegistry) -> McpAdapter:
    """Inicializa y retorna el McpAdapter."""
    adapter = McpAdapter(registry)
    await adapter.initialize()
    return adapter
