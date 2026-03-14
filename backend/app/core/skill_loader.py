import importlib
import inspect
import logging
import os
import pkgutil
from typing import List, Any, Optional, TYPE_CHECKING
from langchain_core.tools import Tool, StructuredTool

if TYPE_CHECKING:
    from app.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Cargador de skills que puede opcionalmente registrar herramientas en ToolRegistry.
    
    Mantiene compatibilidad con el sistema anterior mientras soporta la nueva
    arquitectura de ToolRegistry.
    """
    
    def __init__(self, skills_dir: str = "app/skills", registry: Optional["ToolRegistry"] = None):
        self.skills_dir = skills_dir
        self.registry = registry

    def load_skills(self) -> List[Any]:
        """
        Carga todas las herramientas como una lista plana.
        """
        tools_map = self.load_skills_map()
        all_tools = []
        for tools in tools_map.values():
            all_tools.extend(tools)
        return all_tools

    def load_skills_map(self) -> dict[str, List[Any]]:
        """
        Carga dinámicamente las herramientas y las agrupa por nombre del módulo (skill).
        Retorna: dict { 'calendar': [tool1, tool2], 'browser': [...] }
        """
        skills_map = {}
        
        # Obtener la ruta absoluta del directorio de skills
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        skills_path = os.path.join(base_path, "skills")
        
        if not os.path.exists(skills_path):
            logger.warning(f"Skills directory not found: {skills_path}")
            return {}

        # Iterar sobre los módulos en el directorio
        for module_info in pkgutil.iter_modules([skills_path]):
            module_name_full = f"app.skills.{module_info.name}"
            skill_name = module_info.name # e.g., 'calendar', 'browser'
            skills_map[skill_name] = []
            
            try:
                module = importlib.import_module(module_name_full)
                
                # 1. Buscar lista explícita 'tools'
                if hasattr(module, 'tools') and isinstance(module.tools, list):
                    logger.info(f"Loading explicit tools list from {module_name_full}")
                    for tool in module.tools:
                        if isinstance(tool, (Tool, StructuredTool)):
                            skills_map[skill_name].append(tool)
                        elif callable(tool):
                            # Legacy: wrap raw function in StructuredTool
                            logger.info(f"Auto-wrapping legacy tool function: {tool.__name__}")
                            try:
                                if inspect.iscoroutinefunction(tool):
                                    skills_map[skill_name].append(StructuredTool.from_function(coroutine=tool))
                                else:
                                    skills_map[skill_name].append(StructuredTool.from_function(tool))
                            except ValueError as e:
                                if "docstring" in str(e).lower():
                                    # Skip tools without docstrings to prevent misuse
                                    logger.warning(f"Skipping tool {tool.__name__} due to missing docstring. Docstrings are required for LLM understanding.")
                                    continue
                                else:
                                    logger.error(f"Failed to wrap tool {tool.__name__}: {e}")
                        else:
                            logger.warning(f"Skipping invalid tool in {module_name_full}: {tool}")
                    continue

                # 2. Buscar objetos Tool/StructuredTool individuales (generados por @tool)
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, (Tool, StructuredTool)):
                        logger.info(f"Loading tool '{name}' from {module_name_full}")
                        skills_map[skill_name].append(obj)
                        
            except Exception as e:
                logger.error(f"Error loading skill module {module_name_full}: {e}")

        total_tools = sum(len(t) for t in skills_map.values())
        logger.info(f"Total tools loaded: {total_tools} from {len(skills_map)} skills")
        
        # Si hay un registry, registrar las herramientas
        if self.registry:
            from app.core.tool_registry import ToolMetadata
            for skill_name, tools in skills_map.items():
                for tool in tools:
                    metadata = ToolMetadata(
                        name=tool.name,
                        source="skill",
                        category=self._infer_category(skill_name),
                        description=tool.description or "",
                    )
                    await self.registry.register_tool(tool, metadata)
        
        return skills_map
    
    def _infer_category(self, skill_name: str) -> str:
        """Infiere la categoría de un skill basado en su nombre."""
        skill_lower = skill_name.lower()
        
        categories = {
            "calendar": "productivity",
            "scheduler": "productivity",
            "telegram": "communication",
            "email": "communication",
            "slack": "communication",
            "database": "data",
            "postgres": "data",
            "mysql": "data",
            "github": "development",
            "code_execution": "development",
            "browser": "development",
            "search": "search",
            "brave": "search",
            "duckduckgo": "search",
            "filesystem": "files",
            "drive": "files",
            "google_drive": "files",
            "image_generation": "media",
            "image": "media",
            "memory": "memory",
        }
        
        return categories.get(skill_lower, "utility")
