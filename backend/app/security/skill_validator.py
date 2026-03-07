import ast
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SecurityViolation(Exception):
    pass

class SkillValidator:
    """
    'Customs' component to validate skills before loading.
    Implements static analysis and manifest validation.
    """
    
    FORBIDDEN_BUILTINS = {
        'eval', 'exec', 'compile', 'input', 'breakpoint', '__import__'
    }
    
    FORBIDDEN_IMPORTS = {
        'os.system', 'os.popen', 'os.spawn', 'subprocess', 'shlex',
        'pickle', 'marshal', 'shelve', 'dbm', 'anydbm',
        'telnetlib', 'ftplib', 'smtplib', 'imaplib', 'poplib'
    }

    RESTRICTED_MODULES = {
        'network': {'requests', 'urllib', 'http', 'socket', 'aiohttp', 'httpx'},
        'filesystem': {'os', 'shutil', 'pathlib', 'glob', 'tempfile'}
    }

    def validate_skill(self, skill_path: str) -> bool:
        """
        Validates a complete skill (directory).
        
        Args:
            skill_path: Path to the skill directory.
            
        Returns:
            True if valid.
            
        Raises:
            SecurityViolation: If a severe violation is detected.
            Exception: For other errors.
        """
        try:
            manifest = self._load_manifest(skill_path)
            self._validate_manifest_structure(manifest)
            
            entry_point = manifest.get('entry_point', 'skill_code.py')
            code_path = os.path.join(skill_path, entry_point)
            
            if not os.path.exists(code_path):
                raise SecurityViolation(f"Entry point {entry_point} not found in skill directory.")
            
            self._static_analysis(code_path, manifest)
            
            logger.info(f"Skill at {skill_path} passed validation.")
            return True
            
        except Exception:
            logger.error(f"Skill validation failed for {skill_path}")
            raise

    def _load_manifest(self, skill_path: str) -> Dict[str, Any]:
        manifest_path = os.path.join(skill_path, 'MANIFEST.json')
        if not os.path.exists(manifest_path):
            raise SecurityViolation("MANIFEST.json missing.")
            
        try:
            with open(manifest_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise SecurityViolation("Invalid JSON in MANIFEST.json.")

    def _validate_manifest_structure(self, manifest: Dict[str, Any]):
        required_fields = ['name', 'version', 'permissions', 'entry_point']
        for field in required_fields:
            if field not in manifest:
                raise SecurityViolation(f"Missing required field in MANIFEST.json: {field}")
        
        perms = manifest.get('permissions', {})
        if not isinstance(perms, dict):
            raise SecurityViolation("Permissions field must be a dictionary.")

    def _static_analysis(self, code_path: str, manifest: Dict[str, Any]):
        """
        Performs static analysis of the source code using AST.
        """
        with open(code_path, 'r') as f:
            source = f.read()
            
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise SecurityViolation(f"Syntax error in skill code: {e}")

        permissions = manifest.get('permissions', {})
        allowed_network = permissions.get('network', {}).get('allow_all', False) or \
                          len(permissions.get('network', {}).get('allowed_domains', [])) > 0
        allowed_fs = permissions.get('filesystem', {}).get('allow_all', False) or \
                     len(permissions.get('filesystem', {}).get('read_paths', [])) > 0 or \
                     len(permissions.get('filesystem', {}).get('write_paths', [])) > 0

        # Enforce definition-only policy for top-level code (SecureSkillLoader safety)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
                 # Allow assignments for constants, but disallow expressions (calls)
                 # Strictly speaking, Assign can trigger code if descriptors/metaclasses are involved,
                 # but avoiding explicit Expr/Call at top level handles the most common side-effects.
                 if isinstance(node, ast.Expr):
                      # Ignore docstrings
                      if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                          continue
                      raise SecurityViolation(f"Top-level executable code detected: {type(node).__name__}. Only definitions are allowed.")

        for node in ast.walk(tree):
            # 1. Detect Forbidden Builtins (eval, exec, etc.)
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'builtins':
                    func_name = node.func.attr
                
                if func_name:
                    if func_name in self.FORBIDDEN_BUILTINS:
                        raise SecurityViolation(f"Forbidden function call detected: {func_name}")
                    if not allowed_fs and func_name == 'open':
                         raise SecurityViolation("Filesystem access ('open') detected but filesystem permission not granted.")
            
            # 2. Detect Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    
                    # Check against restricted modules based on permissions
                    if not allowed_network and module_name in self.RESTRICTED_MODULES['network']:
                        raise SecurityViolation(f"Network module '{module_name}' imported but network permission not granted.")
                    
                    if not allowed_fs and module_name in self.RESTRICTED_MODULES['filesystem']:
                        raise SecurityViolation(f"Filesystem module '{module_name}' imported but filesystem permission not granted.")
                        
                    # Check specific dangerous modules (subprocess, etc.)
                    if module_name in self.FORBIDDEN_IMPORTS or alias.name in self.FORBIDDEN_IMPORTS:
                        raise SecurityViolation(f"Forbidden module import detected: {alias.name}")

            # 3. Detect os.system style calls (Attribute calls)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # Check for things like os.system, subprocess.call (if import passed somehow)
                    attr_name = node.func.attr
                    # We can't easily resolve the object type statically, but we can flag suspicious attributes
                    # combined with common module names if we track variables (complex).
                    # For now, rely on import restrictions + known dangerous attributes if possible.
                    pass

        logger.info(f"Static analysis passed for {code_path}")
