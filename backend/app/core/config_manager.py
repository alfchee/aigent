import os
import time
import re
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
MODEL_NAME_RE = re.compile(r"^gemini-[a-z0-9][a-z0-9\.-]*$", re.IGNORECASE)


def _normalize_model_name(model_name: str) -> str:
    value = (model_name or "").strip()
    if value.startswith("models/"):
        value = value[7:]
    return value


def _is_allowed_model(model_name: str) -> bool:
    value = _normalize_model_name(model_name)
    if not value:
        return False
    if value in ALLOWED_MODELS:
        return True
    return bool(MODEL_NAME_RE.match(value))


class ModelConfig(BaseModel):
    name: str
    temperature: float = 0.7
    top_p: float = 0.95
    max_output_tokens: int = 8192


class RoutingConfig(BaseModel):
    default_model: str = "gemini-flash-latest"
    force_upgrade_on_tools: list[str] = ["execute_python", "read_web_content"]
    auto_retry_with_pro: bool = True
    retry_triggers: list[str] = [
        "SyntaxError",
        "ModuleNotFoundError",
        "I cannot complete the request",
        "404",
        "Internal Server Error"
    ]


class LimitsConfig(BaseModel):
    execution_timeout_seconds: int = 300
    max_search_results: int = 5
    max_retries: int = 1


class AppSettings(BaseModel):
    current_model: str = "gemini-flash-latest"
    fallback_model: str = "gemini-2.5-pro"
    auto_escalate: bool = True
    system_prompt: str = ""
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    
    # New configurations
    routing_config: RoutingConfig = Field(default_factory=RoutingConfig)
    limits_config: LimitsConfig = Field(default_factory=LimitsConfig)
    google_workspace_config: dict[str, Any] = Field(default_factory=dict)
    
    # Store the raw JSON for the "Command Center" advanced editor
    model_routing_json: dict[str, Any] = Field(default_factory=dict)


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
    # Default routing logic as per proposal
    routing_defaults = RoutingConfig()
    limits_defaults = LimitsConfig()
    
    # Construct the full model_routing.json structure for the editor
    model_routing_json = {
        "available_models": [
            {
                "id": "gemini-flash-latest",
                "alias": "fast",
                "label": "⚡ Fast (Gemini Flash)",
                "capabilities": ["web_search", "general_chat", "simple_file_read"]
            },
            {
                "id": "gemini-2.5-pro",
                "alias": "smart",
                "label": "🧠 Smart (Gemini Pro)",
                "capabilities": ["complex_coding", "data_analysis", "deep_research"]
            }
        ],
        "routing_logic": routing_defaults.model_dump(),
        "parameters": {
            "temperature_map": {
                "coding": 0.1,
                "creative": 0.8,
                "default": 0.4
            }
        }
    }

    return AppSettings(
        current_model="gemini-flash-latest",
        fallback_model="gemini-2.5-pro",
        auto_escalate=True,
        system_prompt="""# PROTOCOLO DE MEMORIA Y APRENDIZAJE
Eres NaviBot. Tienes acceso a tu propia memoria a largo plazo a través de herramientas.
IMPORTANTE SOBRE TU MEMORIA:
1. No tienes memoria infinita de la conversación.
2. Si el usuario te pregunta sobre algo que discutieron en el pasado (ayer, semana pasada), DEBES usar la herramienta `search_memory_tool`.
3. Si el usuario te da un dato nuevo importante (ej: "Mi API Key es X", "Me mudé a Madrid"), DEBES usar la herramienta `save_memory_tool`.
4. Para charlas casuales ("Hola", "¿Cómo estás?"), NO uses la memoria. Responde rápido.

# GOOGLE WORKSPACE PROTOCOL
- Tienes permiso para interactuar con Google Sheets.
- Al crear un documento, SIEMPRE proporciona el enlace resultante al usuario.
- Si los datos son masivos, procésalos primero con 'execute_python' usando DataFrames y luego envía la lista final de valores a la API de Sheets.
- Cuando el usuario pida "investigar y guardar", realiza primero la búsqueda web profunda, sintetiza y luego estructura la información en filas y columnas.
- **MANEJO DE ERRORES DE AUTH**: Si alguna herramienta de Google (Drive, Sheets, Calendar) falla por falta de credenciales o error de autenticación, NO pidas disculpas. INVOCA INMEDIATAMENTE la herramienta `get_google_oauth_authorization_url` para proporcionar el enlace de acceso al usuario.

# NUEVA REGLA DE DRIVE:
- Si el usuario menciona una carpeta como "Finanzas", primero usa search_drive('Finanzas') para obtener el ID.
- Usa list_drive_files(folder_id) para ver qué hay dentro.
- Si necesitas analizar un archivo (CSV, XLSX, TXT), usa download_file_from_drive para traerlo a tu entorno local y luego usa execute_python para leerlo.

# CALENDAR SOP
- Tienes acceso total al Google Calendar del usuario.
- Fecha y Hora actual (Contexto): {CURRENT_DATETIME}
- AL CREAR EVENTOS:
  1. SIEMPRE verifica primero la disponibilidad usando `list_upcoming_events`.
  2. Genera los timestamps de inicio y fin en formato ISO 8601 estricto (YYYY-MM-DDTHH:MM:SS).
  3. Si el usuario no especifica duración, asume 1 hora por defecto.
- Si el usuario dice "Agenda una reunión mañana a las 10", calcula la fecha basándote en la fecha actual.""",
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
        routing_config=routing_defaults,
        limits_config=limits_defaults,
        google_workspace_config={
            "owner_email": "alfchee@gmail.com",
            "auth_mode": "oauth"
        },
        model_routing_json=model_routing_json
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
    
    # New settings
    routing_config_data = get_app_setting("routing_config")
    limits_config_data = get_app_setting("limits_config")
    google_workspace_config_data = get_app_setting("google_workspace_config")
    model_routing_json_data = get_app_setting("model_routing_json")

    updates: dict[str, Any] = {}
    if isinstance(current_model, str) and current_model.strip():
        updates["current_model"] = current_model.strip()
    if isinstance(fallback_model, str) and fallback_model.strip():
        updates["fallback_model"] = fallback_model.strip()
    if auto_escalate is not None:
        updates["auto_escalate"] = _coerce_bool(auto_escalate, base.auto_escalate)
    if isinstance(system_prompt, str):
        updates["system_prompt"] = system_prompt
        
    if isinstance(routing_config_data, dict):
        updates["routing_config"] = RoutingConfig(**routing_config_data)
    if isinstance(limits_config_data, dict):
        updates["limits_config"] = LimitsConfig(**limits_config_data)
    if isinstance(google_workspace_config_data, dict):
        updates["google_workspace_config"] = google_workspace_config_data
    if isinstance(model_routing_json_data, dict):
        updates["model_routing_json"] = model_routing_json_data
        # Also sync routing_config from this JSON if present, as the JSON is the "master" in UI
        if "routing_logic" in model_routing_json_data:
            updates["routing_config"] = RoutingConfig(**model_routing_json_data["routing_logic"])

    return base.model_copy(update=updates)


def _is_valid_current_model(model_name: str) -> bool:
    value = _normalize_model_name(model_name)
    if value in FAST_MODELS:
        return True
    return _is_allowed_model(value)


def _is_valid_fallback_model(model_name: str) -> bool:
    value = _normalize_model_name(model_name)
    if value in FALLBACK_MODELS:
        return True
    return _is_allowed_model(value)


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
    allowed_keys = {
        "current_model", "fallback_model", "auto_escalate", "system_prompt",
        "routing_config", "limits_config", "model_routing_json", "google_workspace_config"
    }
    for key in list(payload.keys()):
        if key not in allowed_keys:
            payload.pop(key, None)

    if "current_model" in payload:
        value = _normalize_model_name(str(payload["current_model"] or ""))
        if value and not _is_valid_current_model(value):
            raise ValueError("current_model inválido")
        if value:
            set_app_setting("current_model", value)
    if "fallback_model" in payload:
        value = _normalize_model_name(str(payload["fallback_model"] or ""))
        if value and not _is_valid_fallback_model(value):
            raise ValueError("fallback_model inválido")
        if value:
            set_app_setting("fallback_model", value)
    if "auto_escalate" in payload:
        set_app_setting("auto_escalate", bool(payload["auto_escalate"]))
    if "system_prompt" in payload:
        set_app_setting("system_prompt", str(payload["system_prompt"] or ""))
        
    if "limits_config" in payload:
        set_app_setting("limits_config", payload["limits_config"])
        
    if "google_workspace_config" in payload:
        set_app_setting("google_workspace_config", payload["google_workspace_config"])
        
    if "model_routing_json" in payload:
        # If user updates the master JSON, we save it AND update the derived routing_config
        json_data = payload["model_routing_json"]
        set_app_setting("model_routing_json", json_data)
        if isinstance(json_data, dict) and "routing_logic" in json_data:
            set_app_setting("routing_config", json_data["routing_logic"])
    elif "routing_config" in payload:
        # If user updates just the routing config (e.g. from simpler UI), we save it
        set_app_setting("routing_config", payload["routing_config"])

    return get_settings(force_reload=True)


def get_session_model(session_id: str) -> Optional[str]:
    value = get_session_model_setting(session_id)
    if not value:
        return None
    name = _normalize_model_name(value)
    if not name or not _is_allowed_model(name):
        return None
    return name


def set_session_model(session_id: str, model_name: str) -> None:
    name = _normalize_model_name(model_name)
    if not _is_allowed_model(name):
        raise ValueError("model_name inválido")
    set_session_model_setting(session_id=session_id, model_name=name)


def resolve_model(session_id: str, requested_model: Optional[str] = None) -> str:
    explicit = _normalize_model_name(requested_model or "")
    if explicit:
        if not _is_allowed_model(explicit):
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
