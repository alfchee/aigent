import importlib
import inspect
import logging
import os
import pkgutil
from typing import List, Any
from langchain_core.tools import Tool, StructuredTool

logger = logging.getLogger(__name__)

class SkillLoader:
    def __init__(self, skills_dir: str = "app/skills"):
        self.skills_dir = skills_dir

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
                                skills_map[skill_name].append(StructuredTool.from_function(tool))
                            except ValueError as e:
                                if "docstring" in str(e).lower():
                                    # Fallback for missing docstring
                                    logger.warning(f"Tool {tool.__name__} has no docstring. Using name as description.")
                                    skills_map[skill_name].append(StructuredTool.from_function(tool, description=f"Tool: {tool.__name__}"))
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
        return skills_map
