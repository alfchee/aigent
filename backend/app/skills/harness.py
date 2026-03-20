"""
Tool Harness: Pre-validación de arguments y categorización de errores
para tools que llaman APIs externas (Brave, web, archivos).

Capa ortogonal a la validación Pydantic del registry — actúa ANTES
de ejecutar cualquier tool que dependa de recursos externos.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Type

from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.skills.harness")


class ValidationError(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description")
    field: str | None = Field(default=None, description="Which field failed, if any")


@dataclass
class HarnessResult:
    ok: bool
    value: Any = None
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def success(cls, value: Any) -> "HarnessResult":
        return cls(ok=True, value=value)

    @classmethod
    def failure(cls, code: str, message: str, field: str | None = None) -> "HarnessResult":
        return cls(ok=False, errors=[ValidationError(code=code, message=message, field=field)])

    @classmethod
    def failure_multi(cls, errors: list[ValidationError]) -> "HarnessResult":
        return cls(ok=False, errors=errors)


class ToolHarness:
    """
    Registry of per-tool pre-validators that run BEFORE the actual tool execution.
    Each validator receives the raw arguments dict and returns HarnessResult.

    Usage:
        harness.register("smart_search", validate_smart_search_args)
        harness.register("web_browse", validate_web_browse_args)

        result = harness.run("smart_search", {"query": "python", "num_results": 5})
        if not result.ok:
            return result.errors   # abort — do not call the tool
        # proceed to tool.execute(...)
    """

    def __init__(self):
        self._validators: dict[str, Callable[[dict], HarnessResult]] = {}

    def register(self, tool_name: str, validator: Callable[[dict], HarnessResult]) -> None:
        self._validators[tool_name] = validator

    def unregister(self, tool_name: str) -> None:
        self._validators.pop(tool_name, None)

    def run(self, tool_name: str, raw_args: dict) -> HarnessResult:
        validator = self._validators.get(tool_name)
        if not validator:
            return HarnessResult.success(None)
        try:
            return validator(raw_args)
        except Exception as exc:
            logger.exception("Harness validator raised for tool=%s", tool_name)
            return HarnessResult.failure(
                code="harness_internal_error",
                message=str(exc),
            )


harness = ToolHarness()


# ---------------------------------------------------------------------------
# Built-in validators
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
MAX_URL_LENGTH = 2000


def validate_web_browse_args(args: dict) -> HarnessResult:
    """
    Validates arguments for the web_browse tool before execution.
    - url must be a valid http(s) URL
    - url length must be within safe limits
    - session_id must be safe for filesystem use
    """
    errors: list[ValidationError] = []

    url = args.get("url")
    if not url:
        errors.append(ValidationError(code="url_required", message="url is required", field="url"))
    elif not isinstance(url, str):
        errors.append(ValidationError(code="url_not_string", message="url must be a string", field="url"))
    elif len(url) > MAX_URL_LENGTH:
        errors.append(
            ValidationError(
                code="url_too_long",
                message=f"URL exceeds {MAX_URL_LENGTH} characters",
                field="url",
            )
        )
    elif not URL_RE.match(url):
        errors.append(
            ValidationError(
                code="url_invalid",
                message="url must be a valid http:// or https:// URL",
                field="url",
            )
        )

    session_id = args.get("session_id", "default")
    if not isinstance(session_id, str) or "/" in session_id or "\\" in session_id:
        errors.append(
            ValidationError(
                code="session_id_unsafe",
                message="session_id must not contain path separators",
                field="session_id",
            )
        )

    return HarnessResult.failure_multi(errors) if errors else HarnessResult.success(None)


def validate_smart_search_args(args: dict) -> HarnessResult:
    """
    Validates arguments for the smart_search tool before execution.
    - query must be non-empty and within reasonable length
    - num_results must be in allowed range
    - search_type must be one of the supported types
    """
    errors: list[ValidationError] = []

    query = args.get("query")
    if not query:
        errors.append(ValidationError(code="query_required", message="query is required", field="query"))
    elif not isinstance(query, str):
        errors.append(ValidationError(code="query_not_string", message="query must be a string", field="query"))
    elif len(query) > 500:
        errors.append(
            ValidationError(
                code="query_too_long",
                message="query exceeds 500 characters",
                field="query",
            )
        )
    elif len(query.strip()) < 2:
        errors.append(
            ValidationError(
                code="query_too_short",
                message="query must be at least 2 characters",
                field="query",
            )
        )

    num_results = args.get("num_results", 5)
    if not isinstance(num_results, int) or num_results < 1 or num_results > 20:
        errors.append(
            ValidationError(
                code="num_results_out_of_range",
                message="num_results must be between 1 and 20",
                field="num_results",
            )
        )

    search_type = args.get("search_type", "web")
    if search_type not in {"web", "news", "videos"}:
        errors.append(
            ValidationError(
                code="search_type_invalid",
                message="search_type must be one of: web, news, videos",
                field="search_type",
            )
        )

    return HarnessResult.failure_multi(errors) if errors else HarnessResult.success(None)


def validate_read_artifact_args(args: dict) -> HarnessResult:
    """
    Validates arguments for the read_artifact tool before execution.
    - session_id must not contain path separators
    - filename must not contain path traversal attempts
    """
    errors: list[ValidationError] = []

    session_id = args.get("session_id", "default")
    if not isinstance(session_id, str) or "/" in session_id or "\\" in session_id or ".." in session_id:
        errors.append(
            ValidationError(
                code="session_id_unsafe",
                message="session_id must not contain path separators or '..'",
                field="session_id",
            )
        )

    filename = args.get("filename", "")
    if not filename:
        errors.append(ValidationError(code="filename_required", message="filename is required", field="filename"))
    elif ".." in filename or filename.startswith("/") or "\\" in filename:
        errors.append(
            ValidationError(
                code="filename_traversal",
                message="filename must not contain '..' or absolute paths",
                field="filename",
            )
        )

    return HarnessResult.failure_multi(errors) if errors else HarnessResult.success(None)


harness.register("web_browse", validate_web_browse_args)
harness.register("smart_search", validate_smart_search_args)
harness.register("read_artifact", validate_read_artifact_args)
