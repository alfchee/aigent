"""
ToolRegistry - Registro unificado de herramientas

Este módulo implementa el patrón de registro unificado para todas las herramientas
del sistema (Skills locales y herramientas MCP), siguiendo las mejores prácticas
de LangChain y el paper arxiv 2603.05344v1 sobre Tool Learning.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)


# Categorías válidas para herramientas
TOOL_CATEGORIES = {
    "productivity",    # Productividad (calendario, notas, etc.)
    "communication",   # Comunicación (telegram, email, etc.)
    "data",           # Datos (database, spreadsheet, etc.)
    "development",    # Desarrollo (github, code execution, etc.)
    "search",         # Búsqueda web
    "files",          # Archivos y filesystem
    "media",          # Generación de medios (imágenes, etc.)
    "memory",         # Memoria y contexto
    "utility",        # Utilidades varias
}


# Fuentes válidas para herramientas
TOOL_SOURCES = {
    "skill",   # Herramienta local (skill)
    "mcp",     # Herramienta de servidor MCP
}


@dataclass
class ToolMetadata:
    """Metadata para una herramienta registrada."""
    name: str
    source: str  # "skill" | "mcp"
    server: Optional[str] = None  # Nombre del servidor MCP si source == "mcp"
    category: str = "utility"
    description: str = ""
    is_available: bool = True
    last_error: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Valida los valores de los campos."""
        if self.source not in TOOL_SOURCES:
            raise ValueError(f"Invalid source: {self.source}. Must be one of {TOOL_SOURCES}")
        if self.category not in TOOL_CATEGORIES:
            logger.warning(f"Unknown category: {self.category}, defaulting to 'utility'")
            self.category = "utility"


class ToolRegistry:
    """
    Registro centralizado y unificado de todas las herramientas disponibles.
    
    Este registro actúa como "Single Source of Truth" para todas las herramientas
    del sistema, tanto skills locales como herramientas MCP.
    
    Uso:
        registry = ToolRegistry()
        await registry.initialize()
        tools = await registry.get_all_tools()
    """
    
    _instance: Optional["ToolRegistry"] = None
    _lock: asyncio.Lock = None
    
    def __new__(cls):
        """Implementa singleton para el registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Inicializa el registry si no ha sido inicializado."""
        if self._initialized:
            return
            
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._tools_by_source: Dict[str, Set[str]] = {
            "skill": set(),
            "mcp": set(),
        }
        self._tools_by_category: Dict[str, Set[str]] = {
            cat: set() for cat in TOOL_CATEGORIES
        }
        self._tools_by_server: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._initialized = True
        self._initialized_properly = False
        
        logger.info("ToolRegistry instance created")
    
    @property
    def is_initialized(self) -> bool:
        """Retorna si el registry ha sido completamente inicializado."""
        return self._initialized_properly
    
    async def initialize(self) -> None:
        """
        Inicializa el registry cargando skills y MCPs.
        
        Este método debe ser llamado al iniciar la aplicación.
        """
        async with self._lock:
            if self._initialized_properly:
                logger.info("ToolRegistry already initialized")
                return
                
            logger.info("Initializing ToolRegistry...")
            
            # Cargar skills
            await self._load_skills()
            
            # Cargar MCPs (se hace en otra fase)
            # await self._load_mcps()
            
            self._initialized_properly = True
            logger.info(f"ToolRegistry initialized with {len(self._tools)} tools")
    
    async def _load_skills(self) -> None:
        """Carga todos los skills locales."""
        try:
            from app.core.skill_loader import SkillLoader
            loader = SkillLoader()
            skills_map = loader.load_skills_map()
            
            for skill_name, tools in skills_map.items():
                for tool in tools:
                    await self.register_tool(
                        tool=tool,
                        metadata=ToolMetadata(
                            name=tool.name,
                            source="skill",
                            category=self._infer_category(skill_name),
                            description=tool.description or "",
                        )
                    )
                    
            logger.info(f"Loaded {len(self._tools_by_source['skill'])} skill tools")
        except Exception as e:
            logger.error(f"Error loading skills: {e}")
    
    def _infer_category(self, skill_name: str) -> str:
        """Infiere la categoría de un skill basado en su nombre."""
        skill_lower = skill_name.lower()
        
        if skill_lower in ("calendar", "scheduler"):
            return "productivity"
        elif skill_lower in ("telegram", "email", "slack"):
            return "communication"
        elif skill_lower in ("database", "postgres", "mysql"):
            return "data"
        elif skill_lower in ("github", "code_execution", "browser"):
            return "development"
        elif skill_lower in ("search", "brave", "duckduckgo"):
            return "search"
        elif skill_lower in ("filesystem", "drive", "google_drive"):
            return "files"
        elif skill_lower in ("image_generation", "image"):
            return "media"
        elif skill_lower in ("memory",):
            return "memory"
        else:
            return "utility"
    
    async def register_tool(
        self, 
        tool: BaseTool, 
        metadata: ToolMetadata,
        overwrite: bool = False
    ) -> bool:
        """
        Registra una herramienta con su metadata.
        
        Args:
            tool: Instancia de BaseTool (LangChain)
            metadata: Metadata de la herramienta
            overwrite: Si True, permite sobrescribir herramientas existentes
            
        Returns:
            True si se registró correctamente, False si ya existía
        """
        async with self._lock:
            tool_name = metadata.name or tool.name
            
            # Validar que la herramienta tiene nombre
            if not tool_name:
                logger.error("Cannot register tool without name")
                return False
            
            # Verificar si ya existe
            if tool_name in self._tools and not overwrite:
                logger.warning(f"Tool {tool_name} already registered, skipping")
                return False
            
            # Registrar
            self._tools[tool_name] = tool
            self._metadata[tool_name] = metadata
            
            # Actualizar índices
            self._tools_by_source[metadata.source].add(tool_name)
            self._tools_by_category[metadata.category].add(tool_name)
            
            if metadata.server:
                if metadata.server not in self._tools_by_server:
                    self._tools_by_server[metadata.server] = set()
                self._tools_by_server[metadata.server].add(tool_name)
            
            logger.debug(f"Registered tool: {tool_name} (source: {metadata.source})")
            return True
    
    async def unregister_tool(self, name: str) -> bool:
        """
        Desregistra una herramienta.
        
        Args:
            name: Nombre de la herramienta
            
        Returns:
            True si se desregistró, False si no existía
        """
        async with self._lock:
            if name not in self._tools:
                return False
            
            # Obtener metadata para limpiar índices
            metadata = self._metadata.get(name)
            
            # Limpiar índices
            if metadata:
                self._tools_by_source[metadata.source].discard(name)
                self._tools_by_category[metadata.category].discard(name)
                if metadata.server:
                    self._tools_by_server.get(metadata.server, set()).discard(name)
            
            # Eliminar
            del self._tools[name]
            if name in self._metadata:
                del self._metadata[name]
            
            logger.debug(f"Unregistered tool: {name}")
            return True
    
    async def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Obtiene una herramienta por nombre.
        
        Args:
            name: Nombre de la herramienta
            
        Returns:
            La herramienta o None si no existe
        """
        return self._tools.get(name)
    
    async def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """
        Obtiene la metadata de una herramienta.
        
        Args:
            name: Nombre de la herramienta
            
        Returns:
            La metadata o None si no existe
        """
        return self._metadata.get(name)
    
    async def get_all_tools(self) -> List[BaseTool]:
        """
        Retorna todas las herramientas disponibles.
        
        Returns:
            Lista de herramientas
        """
        return list(self._tools.values())
    
    async def get_tools_by_source(self, source: str) -> List[BaseTool]:
        """
        Retorna herramientas filtradas por source.
        
        Args:
            source: "skill" o "mcp"
            
        Returns:
            Lista de herramientas del source especificado
        """
        if source not in self._tools_by_source:
            return []
        
        tool_names = self._tools_by_source[source]
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    async def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        Retorna herramientas filtradas por categoría.
        
        Args:
            category: Categoría de las herramientas
            
        Returns:
            Lista de herramientas de la categoría especificada
        """
        if category not in self._tools_by_category:
            return []
        
        tool_names = self._tools_by_category[category]
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    async def get_tools_by_server(self, server: str) -> List[BaseTool]:
        """
        Retorna herramientas de un servidor MCP específico.
        
        Args:
            server: Nombre del servidor MCP
            
        Returns:
            Lista de herramientas del servidor
        """
        tool_names = self._tools_by_server.get(server, set())
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    async def update_tool_availability(
        self, 
        name: str, 
        is_available: bool,
        error: Optional[str] = None
    ) -> bool:
        """
        Actualiza la disponibilidad de una herramienta.
        
        Args:
            name: Nombre de la herramienta
            is_available: Si la herramienta está disponible
            error: Error que causó la indisponibilidad (opcional)
            
        Returns:
            True si se actualizó correctamente
        """
        async with self._lock:
            if name not in self._metadata:
                return False
            
            metadata = self._metadata[name]
            metadata.is_available = is_available
            metadata.last_error = error
            
            return True
    
    async def reload_tools(self) -> None:
        """Recarga todas las herramientas."""
        async with self._lock:
            # Limpiar todo
            self._tools.clear()
            self._metadata.clear()
            self._tools_by_source = {"skill": set(), "mcp": set()}
            self._tools_by_category = {cat: set() for cat in TOOL_CATEGORIES}
            self._tools_by_server.clear()
            self._initialized_properly = False
            
            # Recargar
            await self._load_skills()
            self._initialized_properly = True
            
            logger.info("ToolRegistry reloaded")
    
    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """
        Verifica el estado de todas las herramientas.
        
        Returns:
            Dict con el estado de cada herramienta
        """
        results = {}
        
        for name, metadata in self._metadata.items():
            results[name] = {
                "available": metadata.is_available,
                "source": metadata.source,
                "category": metadata.category,
                "server": metadata.server,
                "last_error": metadata.last_error,
            }
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del registry.
        
        Returns:
            Dict con estadísticas
        """
        return {
            "total_tools": len(self._tools),
            "by_source": {
                source: len(tools) 
                for source, tools in self._tools_by_source.items()
            },
            "by_category": {
                cat: len(tools)
                for cat, tools in self._tools_by_category.items()
            },
            "by_server": {
                server: len(tools)
                for server, tools in self._tools_by_server.items()
            },
            "initialized": self._initialized_properly,
        }
    
    def clear_instance(self) -> None:
        """Limpia la instancia (para testing)."""
        self._tools.clear()
        self._metadata.clear()
        self._tools_by_source = {"skill": set(), "mcp": set()}
        self._tools_by_category = {cat: set() for cat in TOOL_CATEGORIES}
        self._tools_by_server.clear()
        self._initialized_properly = False
        ToolRegistry._instance = None


# Singleton accessor
_tool_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Obtiene la instancia singleton del ToolRegistry."""
    global _tool_registry_instance
    if _tool_registry_instance is None:
        _tool_registry_instance = ToolRegistry()
    return _tool_registry_instance


async def initialize_tool_registry() -> ToolRegistry:
    """Inicializa y retorna el ToolRegistry."""
    registry = get_tool_registry()
    await registry.initialize()
    return registry
