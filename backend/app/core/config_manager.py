import os
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.persistence import (
    get_app_setting,
    get_session_model_setting,
    set_app_setting,
    set_session_model_setting,
)

FAST_MODELS = [
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]

FALLBACK_MODELS = [
    "gemini-3-pro-preview",
    "gemini-2.5-pro",
]

ALLOWED_MODELS = set(FAST_MODELS + FALLBACK_MODELS)


class ModelConfig(BaseModel):
    name: str
    temperature: float = 0.7
    top_p: float = 0.95
    max_output_tokens: int = 8192


class AppSettings(BaseModel):
    current_model: str = "gemini-flash-latest"
    fallback_model: str = "gemini-2.5-pro"
    auto_escalate: bool = True
    system_prompt: str = ""
    models: dict[str, ModelConfig] = Field(default_factory=dict)


_CACHE_TTL_SECONDS = 2.0
_cached_settings: Optional[AppSettings] = None
_cached_at: float = 0.0


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _defaults() -> AppSettings:
    return AppSettings(
        current_model="gemini-flash-latest",
        fallback_model="gemini-2.5-pro",
        auto_escalate=True,
        system_prompt="",
        models={
            "gemini-3-flash-preview": ModelConfig(
                name="gemini-3-flash-preview", temperature=0.7, top_p=0.95, max_output_tokens=8192
            ),
            "gemini-flash-latest": ModelConfig(
                name="gemini-flash-latest", temperature=0.7, top_p=0.95, max_output_tokens=8192
            ),
            "gemini-3-pro-preview": ModelConfig(
                name="gemini-3-pro-preview", temperature=0.7, top_p=0.95, max_output_tokens=8192
            ),
            "gemini-2.5-pro": ModelConfig(name="gemini-2.5-pro", temperature=0.7, top_p=0.95, max_output_tokens=8192),
        },
    )


def _load_from_env(base: AppSettings) -> AppSettings:
    current_model = os.getenv("NAVIBOT_CURRENT_MODEL") or base.current_model
    fallback_model = os.getenv("NAVIBOT_FALLBACK_MODEL") or base.fallback_model
    auto_escalate = _coerce_bool(os.getenv("NAVIBOT_AUTO_ESCALATE"), base.auto_escalate)
    system_prompt = os.getenv("NAVIBOT_SYSTEM_PROMPT")
    if system_prompt is None:
        system_prompt = base.system_prompt
    return base.model_copy(
        update={
            "current_model": current_model,
            "fallback_model": fallback_model,
            "auto_escalate": auto_escalate,
            "system_prompt": system_prompt,
        }
    )


def _load_from_db(base: AppSettings) -> AppSettings:
    current_model = get_app_setting("current_model")
    fallback_model = get_app_setting("fallback_model")
    auto_escalate = get_app_setting("auto_escalate")
    system_prompt = get_app_setting("system_prompt")

    updates: dict[str, Any] = {}
    if isinstance(current_model, str) and current_model.strip():
        updates["current_model"] = current_model.strip()
    if isinstance(fallback_model, str) and fallback_model.strip():
        updates["fallback_model"] = fallback_model.strip()
    if auto_escalate is not None:
        updates["auto_escalate"] = _coerce_bool(auto_escalate, base.auto_escalate)
    if isinstance(system_prompt, str):
        updates["system_prompt"] = system_prompt

    return base.model_copy(update=updates)


def _is_valid_current_model(model_name: str) -> bool:
    return (model_name or "").strip() in FAST_MODELS


def _is_valid_fallback_model(model_name: str) -> bool:
    return (model_name or "").strip() in FALLBACK_MODELS


def _repair_db_settings_if_needed(defaults: AppSettings) -> None:
    try:
        current_model = get_app_setting("current_model")
        if isinstance(current_model, str) and current_model.strip() and not _is_valid_current_model(current_model):
            set_app_setting("current_model", defaults.current_model)
        fallback_model = get_app_setting("fallback_model")
        if isinstance(fallback_model, str) and fallback_model.strip() and not _is_valid_fallback_model(fallback_model):
            set_app_setting("fallback_model", defaults.fallback_model)
    except Exception:
        return


def _sanitize_settings(s: AppSettings, defaults: AppSettings) -> AppSettings:
    updates: dict[str, Any] = {}
    if not _is_valid_current_model(s.current_model):
        updates["current_model"] = defaults.current_model
    if not _is_valid_fallback_model(s.fallback_model):
        updates["fallback_model"] = defaults.fallback_model
    if updates:
        return s.model_copy(update=updates)
    return s


def get_settings(force_reload: bool = False) -> AppSettings:
    global _cached_settings, _cached_at
    now = time.time()
    if not force_reload and _cached_settings is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_settings

    defaults = _defaults()
    _repair_db_settings_if_needed(defaults)

    s = defaults
    s = _load_from_env(s)
    s = _load_from_db(s)
    s = _sanitize_settings(s, defaults)

    _cached_settings = s
    _cached_at = now
    return s


def update_settings(payload: dict[str, Any]) -> AppSettings:
    allowed_keys = {"current_model", "fallback_model", "auto_escalate", "system_prompt"}
    for key in list(payload.keys()):
        if key not in allowed_keys:
            payload.pop(key, None)

    if "current_model" in payload:
        value = str(payload["current_model"] or "").strip()
        if value and not _is_valid_current_model(value):
            raise ValueError("current_model inválido")
        if value:
            set_app_setting("current_model", value)
    if "fallback_model" in payload:
        value = str(payload["fallback_model"] or "").strip()
        if value and not _is_valid_fallback_model(value):
            raise ValueError("fallback_model inválido")
        if value:
            set_app_setting("fallback_model", value)
    if "auto_escalate" in payload:
        set_app_setting("auto_escalate", bool(payload["auto_escalate"]))
    if "system_prompt" in payload:
        set_app_setting("system_prompt", str(payload["system_prompt"] or ""))

    return get_settings(force_reload=True)


def get_session_model(session_id: str) -> Optional[str]:
    value = get_session_model_setting(session_id)
    if not value:
        return None
    name = value.strip()
    if not name or name not in ALLOWED_MODELS:
        return None
    return name


def set_session_model(session_id: str, model_name: str) -> None:
    name = (model_name or "").strip()
    if name not in ALLOWED_MODELS:
        raise ValueError("model_name inválido")
    set_session_model_setting(session_id=session_id, model_name=name)


def resolve_model(session_id: str, requested_model: Optional[str] = None) -> str:
    explicit = (requested_model or "").strip()
    if explicit:
        if explicit not in ALLOWED_MODELS:
            raise ValueError("model_name inválido")
        return explicit
    session_value = get_session_model(session_id)
    if session_value:
        return session_value
    return get_settings().current_model


def provider_status() -> dict[str, bool]:
    return {
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "brave": bool(os.getenv("BRAVE_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
    }
