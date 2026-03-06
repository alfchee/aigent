
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Configure simple logging for standalone script usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

logger = logging.getLogger("navibot.dependency_verifier")

@dataclass
class DependencyStatus:
    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None
    error: Optional[str] = None
    permissions: Optional[str] = None

@dataclass
class EnvironmentReport:
    python_executable: str
    python_version: str
    sys_path: List[str]
    dependencies: Dict[str, DependencyStatus] = field(default_factory=dict)
    missing_count: int = 0
    success: bool = False

class DependencyVerifier:
    def __init__(self, required_deps: List[str]):
        self.required_deps = required_deps
        self.report = EnvironmentReport(
            python_executable=sys.executable,
            python_version=sys.version,
            sys_path=sys.path
        )

    def verify(self) -> EnvironmentReport:
        logger.info("Starting dependency verification")
        missing_count = 0
        
        for dep in self.required_deps:
            status = self._check_dependency(dep)
            self.report.dependencies[dep] = status
            if not status.installed:
                missing_count += 1
                logger.error(f"Dependency missing or inaccessible: {dep} - Reason: {status.error}")
            else:
                logger.info(f"Dependency verified: {dep} ({status.version}) at {status.path}")

        self.report.missing_count = missing_count
        self.report.success = (missing_count == 0)
        return self.report

    def _check_dependency(self, name: str) -> DependencyStatus:
        try:
            spec = importlib.util.find_spec(name)
            if spec is None:
                return DependencyStatus(name=name, installed=False, error="Module not found in sys.path")
            
            # Try to get version and path
            try:
                module = importlib.import_module(name)
                version = getattr(module, "__version__", "unknown")
                path = getattr(module, "__file__", "unknown")
                
                # Check permissions
                perms = "unknown"
                if path and path != "unknown":
                    path_obj = Path(path)
                    if path_obj.exists():
                        mode = path_obj.stat().st_mode
                        r_ok = os.access(path, os.R_OK)
                        perms = f"{oct(mode)[-3:]} (R_OK={r_ok})"
                
                return DependencyStatus(
                    name=name, 
                    installed=True, 
                    version=version, 
                    path=path,
                    permissions=perms
                )
            except ImportError as e:
                return DependencyStatus(name=name, installed=False, error=f"ImportError: {str(e)}")
            except Exception as e:
                return DependencyStatus(name=name, installed=False, error=f"Unexpected error: {str(e)}")

        except Exception as e:
            return DependencyStatus(name=name, installed=False, error=f"Verification failed: {str(e)}")

    def print_report(self):
        print("\n=== Dependency Verification Report ===")
        print(f"Python Executable: {self.report.python_executable}")
        print(f"Status: {'SUCCESS' if self.report.success else 'FAILURE'}")
        print(f"Missing Dependencies: {self.report.missing_count}")
        print("\n--- Details ---")
        for name, status in self.report.dependencies.items():
            mark = "✅" if status.installed else "❌"
            print(f"{mark} {name}:")
            if status.installed:
                print(f"    Version: {status.version}")
                print(f"    Path: {status.path}")
                print(f"    Permissions: {status.permissions}")
            else:
                print(f"    Error: {status.error}")
        print("\n--- sys.path ---")
        for p in self.report.sys_path:
            print(f"  - {p}")
        print("====================================\n")

if __name__ == "__main__":
    # Example usage reading from args or default list
    deps = sys.argv[1:] if len(sys.argv) > 1 else ["numpy", "pandas", "matplotlib", "seaborn"]
    verifier = DependencyVerifier(deps)
    report = verifier.verify()
    verifier.print_report()
    if not report.success:
        sys.exit(1)
