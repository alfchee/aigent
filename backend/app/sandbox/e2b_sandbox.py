from __future__ import annotations

import ast
import asyncio
import logging
import re
import sys
import resource
import time
from threading import Lock
from pathlib import Path
from typing import Dict, List, Optional

from monty.json import jsanitize
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("navibot.sandbox")


class SandboxLimits(BaseModel):
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    max_code_length: int = Field(default=8000, ge=100, le=30000)
    max_output_chars: int = Field(default=12000, ge=500, le=100000)
    cpu_seconds: int = Field(default=4, ge=1, le=30)
    memory_mb: int = Field(default=128, ge=32, le=1024)
    file_size_mb: int = Field(default=8, ge=1, le=128)
    max_open_files: int = Field(default=32, ge=8, le=512)
    max_processes: int = Field(default=1, ge=1, le=32)


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
    role_profiles: Dict[str, SandboxLimits] = Field(
        default_factory=lambda: {
            "default": SandboxLimits(),
            "coder": SandboxLimits(timeout_seconds=20, cpu_seconds=6, memory_mb=256, file_size_mb=24),
            "researcher": SandboxLimits(timeout_seconds=8, cpu_seconds=2, memory_mb=96, file_size_mb=4),
        }
    )
    role_import_allowlist: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "default": ["math", "random", "statistics", "json", "datetime", "time"],
            "coder": [
                "math",
                "random",
                "statistics",
                "json",
                "datetime",
                "time",
                "re",
                "itertools",
                "collections",
                "functools",
                "typing",
                "heapq",
            ],
            "researcher": ["json", "datetime", "time", "math", "statistics", "re"],
        }
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
        self._metrics_lock = Lock()
        self._metrics: Dict[str, Dict[str, float | int]] = {
            "global": {
                "total_runs": 0,
                "success_runs": 0,
                "policy_violations": 0,
                "timeouts": 0,
                "execution_errors": 0,
                "total_duration_ms": 0.0,
            }
        }

    def _resolve_limits(self, role_id: Optional[str]) -> SandboxLimits:
        if role_id and role_id in self.config.role_profiles:
            return self.config.role_profiles[role_id]
        return self.config.role_profiles.get("default", self.config.limits)

    def _resolve_role(self, role_id: Optional[str]) -> str:
        if role_id and role_id in self.config.role_profiles:
            return role_id
        return "default"

    def _resolve_allowlist(self, role_id: str) -> List[str]:
        return self.config.role_import_allowlist.get(
            role_id,
            self.config.role_import_allowlist.get("default", []),
        )

    def _validate_imports(self, code: str, role_id: str) -> Optional[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"Syntax error: {exc.msg}"
        allowlist = set(self._resolve_allowlist(role_id))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowlist:
                        return f"Import '{root}' no permitido para rol '{role_id}'."
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    return "Import relativo no permitido."
                root = node.module.split(".")[0]
                if root not in allowlist:
                    return f"Import from '{root}' no permitido para rol '{role_id}'."
        return None

    def _validate_code(self, code: str, limits: SandboxLimits) -> Optional[str]:
        if len(code) > limits.max_code_length:
            return f"Code exceeds limit of {limits.max_code_length} characters."
        for pattern in self.config.blocked_patterns:
            if re.search(pattern, code):
                return f"Blocked code pattern detected: {pattern}"
        return None

    def _truncate(self, text: str) -> str:
        if len(text) <= self.config.limits.max_output_chars:
            return text
        max_chars = self.config.limits.max_output_chars
        return f"{text[:max_chars]}\n\n...[output truncated]"

    def _record_metric(self, role_id: str, kind: str, duration_ms: float = 0.0) -> None:
        with self._metrics_lock:
            bucket = self._metrics.setdefault(
                role_id,
                {
                    "total_runs": 0,
                    "success_runs": 0,
                    "policy_violations": 0,
                    "timeouts": 0,
                    "execution_errors": 0,
                    "total_duration_ms": 0.0,
                },
            )
            global_bucket = self._metrics["global"]
            for target in (bucket, global_bucket):
                target["total_runs"] += 1
                target["total_duration_ms"] += duration_ms
                if kind == "success":
                    target["success_runs"] += 1
                elif kind == "policy":
                    target["policy_violations"] += 1
                elif kind == "timeout":
                    target["timeouts"] += 1
                else:
                    target["execution_errors"] += 1

    def metrics_snapshot(self) -> Dict[str, Dict[str, float | int]]:
        with self._metrics_lock:
            snapshot: Dict[str, Dict[str, float | int]] = {}
            for key, value in self._metrics.items():
                avg = 0.0
                total_runs = int(value["total_runs"])
                if total_runs > 0:
                    avg = float(value["total_duration_ms"]) / total_runs
                snapshot[key] = {
                    **value,
                    "avg_duration_ms": round(avg, 2),
                }
            return snapshot

    async def execute_code(
        self,
        code: str,
        timeout: int = 30,
        session_id: str = "default",
        role_id: Optional[str] = None,
    ) -> CodeExecutionResult:
        started = time.perf_counter()
        request = CodeExecutionRequest(code=code, timeout=timeout, session_id=session_id)
        resolved_role = self._resolve_role(role_id)
        limits = self._resolve_limits(resolved_role)
        validation_error = self._validate_code(request.code, limits)
        if validation_error:
            self._record_metric(resolved_role, "policy", (time.perf_counter() - started) * 1000)
            return CodeExecutionResult(stdout="", stderr=validation_error, error="PolicyViolation")
        import_error = self._validate_imports(request.code, resolved_role)
        if import_error:
            self._record_metric(resolved_role, "policy", (time.perf_counter() - started) * 1000)
            return CodeExecutionResult(stdout="", stderr=import_error, error="PolicyViolation")

        session_path = self.base_path / request.session_id
        session_path.mkdir(parents=True, exist_ok=True)

        run_timeout = min(request.timeout or limits.timeout_seconds, limits.timeout_seconds)

        def _apply_limits() -> None:
            memory_bytes = limits.memory_mb * 1024 * 1024
            file_bytes = limits.file_size_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
            resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))
            resource.setrlimit(resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes))

        try:
            process = await asyncio.create_subprocess_exec(
                self.config.python_executable,
                "-I",
                "-c",
                request.code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(session_path),
                preexec_fn=_apply_limits,
                env={"PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=run_timeout)
        except asyncio.TimeoutError:
            self._record_metric(resolved_role, "timeout", (time.perf_counter() - started) * 1000)
            return CodeExecutionResult(stdout="", stderr=f"Execution exceeded {run_timeout}s timeout.", error="Timeout")
        except Exception as exc:
            logger.exception("Sandbox execution failed: %s", exc)
            self._record_metric(resolved_role, "error", (time.perf_counter() - started) * 1000)
            return CodeExecutionResult(stdout="", stderr=str(exc), error="ExecutionException")

        artifacts = [str(path.name) for path in session_path.iterdir() if path.is_file()]
        safe_artifacts = jsanitize(artifacts)
        result = CodeExecutionResult(
            stdout=self._truncate(stdout.decode("utf-8", errors="replace")),
            stderr=self._truncate(stderr.decode("utf-8", errors="replace")),
            error=None if process.returncode == 0 else f"ExitCode:{process.returncode}",
            artifacts=safe_artifacts,
        )
        self._record_metric(
            resolved_role,
            "success" if result.error is None else "error",
            (time.perf_counter() - started) * 1000,
        )
        return result


default_sandbox = SecureSandbox()
