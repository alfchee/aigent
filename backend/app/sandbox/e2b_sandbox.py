from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import List, Optional

from monty.json import jsanitize
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("navibot.sandbox")


class SandboxLimits(BaseModel):
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    max_code_length: int = Field(default=8000, ge=100, le=30000)
    max_output_chars: int = Field(default=12000, ge=500, le=100000)


class SandboxConfig(BaseModel):
    base_dir: str = Field(default="/tmp/navibot_sandbox")
    python_executable: str = Field(default=sys.executable)
    limits: SandboxLimits = Field(default_factory=SandboxLimits)
    blocked_patterns: List[str] = Field(
        default_factory=lambda: [
            r"\bimport\s+os\b",
            r"\bimport\s+sys\b",
            r"\bimport\s+subprocess\b",
            r"\bimport\s+socket\b",
            r"\bimport\s+shutil\b",
            r"\bfrom\s+os\s+import\b",
            r"\bfrom\s+subprocess\s+import\b",
            r"\bopen\s*\(",
            r"\beval\s*\(",
            r"\bexec\s*\(",
            r"__import__\s*\(",
        ]
    )


class CodeExecutionResult(BaseModel):
    stdout: str
    stderr: str
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)


class CodeExecutionRequest(BaseModel):
    code: str = Field(min_length=1)
    timeout: Optional[int] = Field(default=None, ge=1, le=60)
    session_id: str = Field(default="default")

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        normalized = value.strip() or "default"
        return re.sub(r"[^a-zA-Z0-9_-]", "_", normalized)[:64]


class SecureSandbox:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.base_path = Path(self.config.base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _validate_code(self, code: str) -> Optional[str]:
        if len(code) > self.config.limits.max_code_length:
            return f"Code exceeds limit of {self.config.limits.max_code_length} characters."
        for pattern in self.config.blocked_patterns:
            if re.search(pattern, code):
                return f"Blocked code pattern detected: {pattern}"
        return None

    def _truncate(self, text: str) -> str:
        if len(text) <= self.config.limits.max_output_chars:
            return text
        max_chars = self.config.limits.max_output_chars
        return f"{text[:max_chars]}\n\n...[output truncated]"

    async def execute_code(self, code: str, timeout: int = 30, session_id: str = "default") -> CodeExecutionResult:
        request = CodeExecutionRequest(code=code, timeout=timeout, session_id=session_id)
        validation_error = self._validate_code(request.code)
        if validation_error:
            return CodeExecutionResult(stdout="", stderr=validation_error, error="PolicyViolation")

        session_path = self.base_path / request.session_id
        session_path.mkdir(parents=True, exist_ok=True)

        run_timeout = request.timeout or self.config.limits.timeout_seconds
        try:
            process = await asyncio.create_subprocess_exec(
                self.config.python_executable,
                "-I",
                "-c",
                request.code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(session_path),
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=run_timeout)
        except asyncio.TimeoutError:
            return CodeExecutionResult(stdout="", stderr=f"Execution exceeded {run_timeout}s timeout.", error="Timeout")
        except Exception as exc:
            logger.exception("Sandbox execution failed: %s", exc)
            return CodeExecutionResult(stdout="", stderr=str(exc), error="ExecutionException")

        artifacts = [str(path.name) for path in session_path.iterdir() if path.is_file()]
        safe_artifacts = jsanitize(artifacts)
        return CodeExecutionResult(
            stdout=self._truncate(stdout.decode("utf-8", errors="replace")),
            stderr=self._truncate(stderr.decode("utf-8", errors="replace")),
            error=None if process.returncode == 0 else f"ExitCode:{process.returncode}",
            artifacts=safe_artifacts,
        )


default_sandbox = SecureSandbox()
