import os
import logging
from typing import Dict, Any, List, Optional
from e2b import Sandbox
from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.sandbox.e2b")

class SandboxConfig(BaseModel):
    """Configuration for E2B Sandbox."""
    api_key: Optional[str] = Field(None, description="E2B API Key")
    template: str = Field("base", description="Template ID for the sandbox")

class CodeExecutionResult(BaseModel):
    """Result of code execution in the sandbox."""
    stdout: str
    stderr: str
    error: Optional[str] = None
    artifacts: List[str] = []

class SecureSandbox:
    """
    Secure Python Sandbox using E2B.
    Provides isolated environment for code execution.
    """
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig(api_key=os.getenv("E2B_API_KEY"))
        self._check_api_key()

    def _check_api_key(self):
        if not self.config.api_key:
            logger.warning("E2B_API_KEY not found. Sandbox execution will fail unless configured.")

    async def execute_code(self, code: str, timeout: int = 30) -> CodeExecutionResult:
        """
        Execute Python code in the sandbox.
        
        Args:
            code: Python code string.
            timeout: Execution timeout in seconds.
            
        Returns:
            CodeExecutionResult object containing stdout, stderr, and artifacts.
        """
        if not self.config.api_key:
            return CodeExecutionResult(
                stdout="",
                stderr="E2B API Key missing. Cannot execute code securely.",
                error="Configuration Error"
            )

        try:
            # Initialize sandbox
            sandbox = Sandbox(api_key=self.config.api_key, template=self.config.template)
            
            # Execute code
            # E2B's run_code returns an object with stdout, stderr, and results
            logger.info("Executing code in E2B Sandbox...")
            
            # Use run_code which handles execution
            execution = sandbox.run_code(code)
            
            # Process results
            stdout = execution.stdout or ""
            stderr = execution.stderr or ""
            error = execution.error
            
            # Close sandbox
            sandbox.close()
            
            return CodeExecutionResult(
                stdout=stdout,
                stderr=stderr,
                error=str(error) if error else None
            )

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return CodeExecutionResult(
                stdout="",
                stderr=str(e),
                error="Execution Exception"
            )

    async def install_packages(self, packages: List[str]):
        """Install Python packages in the sandbox (if persistent sandbox is used)."""
        # E2B allows installing packages via terminal commands
        pass

# Default instance
default_sandbox = SecureSandbox()
