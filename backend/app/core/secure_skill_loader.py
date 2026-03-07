import importlib.util
import inspect
import logging
import os
import sys
from typing import List, Any, Dict
from langchain_core.tools import Tool, StructuredTool

from app.security.skill_validator import SkillValidator, SecurityViolation

logger = logging.getLogger(__name__)

class SecureSkillLoader:
    """
    Loader for secure skills located in /secure_skills.
    Enforces validation before loading.
    """
    
    def __init__(self, secure_skills_dir: str = "secure_skills"):
        # Resolve absolute path relative to project root (assuming we run from project root or backend root)
        # If running from backend/, secure_skills is ../secure_skills
        # But user said /secure_skills in project root.
        # Let's try to find it.
        self.project_root = self._find_project_root()
        self.secure_skills_dir = os.path.join(self.project_root, secure_skills_dir)
        self.validator = SkillValidator()

    def _find_project_root(self) -> str:
        """Finds the project root by looking for secure_skills directory or marker."""
        current = os.path.abspath(os.path.dirname(__file__))
        # Traverse up until we find secure_skills or hit root
        while current != "/":
            if os.path.exists(os.path.join(current, "secure_skills")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        # Fallback to current working directory if not found (might be running from root)
        return os.getcwd()

    def load_skills(self) -> Dict[str, List[Any]]:
        """
        Loads all valid secure skills and returns a map of skill_name -> tools.
        """
        if not os.path.exists(self.secure_skills_dir):
            logger.warning(f"Secure skills directory not found: {self.secure_skills_dir}")
            return {}

        skills_map = {}
        
        # Iterate over subdirectories in secure_skills
        for item in os.listdir(self.secure_skills_dir):
            skill_path = os.path.join(self.secure_skills_dir, item)
            if os.path.isdir(skill_path):
                try:
                    # 1. Validate
                    logger.info(f"Validating secure skill: {item}")
                    if self.validator.validate_skill(skill_path):
                        # 2. Load
                        tools = self._load_skill_module(skill_path, item)
                        if tools:
                            skills_map[item] = tools
                            logger.info(f"Successfully loaded secure skill: {item} ({len(tools)} tools)")
                except SecurityViolation as e:
                    logger.error(f"Security violation loading skill {item}: {e}")
                except Exception as e:
                    logger.error(f"Error loading secure skill {item}: {e}")
        
        return skills_map

    def _load_skill_module(self, skill_path: str, skill_name: str) -> List[Any]:
        """
        Dynamically loads the skill module and extracts tools.
        """
        manifest = self.validator._load_manifest(skill_path)
        entry_point = manifest.get('entry_point', 'skill_code.py')
        module_path = os.path.join(skill_path, entry_point)
        
        spec = importlib.util.spec_from_file_location(f"secure_skills.{skill_name}", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"secure_skills.{skill_name}"] = module
            spec.loader.exec_module(module)
            
            tools = []
            # Extract tools (similar logic to standard SkillLoader)
            
            # 1. Explicit 'tools' list
            if hasattr(module, 'tools') and isinstance(module.tools, list):
                for tool in module.tools:
                    if isinstance(tool, (Tool, StructuredTool)):
                        tools.append(tool)
                    elif callable(tool):
                         # Wrap callable
                        try:
                            if inspect.iscoroutinefunction(tool):
                                tools.append(StructuredTool.from_function(coroutine=tool))
                            else:
                                tools.append(StructuredTool.from_function(tool))
                        except Exception as e:
                            logger.error(f"Failed to wrap secure tool {tool.__name__}: {e}")
                return tools

            # 2. Decorated tools
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, (Tool, StructuredTool)):
                    tools.append(obj)
            
            return tools
        
        return []
