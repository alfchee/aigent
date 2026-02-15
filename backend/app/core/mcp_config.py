import json
import os
import time
from typing import Any

from app.core.persistence import get_app_setting, set_app_setting


CONFIG_KEY = "mcp_active_config"
REGISTRY_KEY = "mcp_registry_custom"
SOURCES_KEY = "mcp_registry_sources"
ENCRYPTED_FLAG = "__encrypted__"


def _get_cipher():
    key = os.getenv("NAVIBOT_MCP_ENCRYPTION_KEY") or os.getenv("NAVIBOT_MCP_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
    except Exception:
        raise ValueError("cryptography no está instalado")
    try:
        return Fernet(key.encode("utf-8"))
    except Exception:
        raise ValueError("clave de cifrado inválida")


def _encrypt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cipher = _get_cipher()
    if cipher is None:
        return payload
    raw = json.dumps(payload, ensure_ascii=False)
    token = cipher.encrypt(raw.encode("utf-8")).decode("utf-8")
    return {ENCRYPTED_FLAG: True, "ciphertext": token, "version": 1}


def _decrypt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cipher = _get_cipher()
    if cipher is None:
        raise ValueError("clave de cifrado requerida para mcp_config")
    token = payload.get("ciphertext")
    if not isinstance(token, str) or not token:
        return {}
    try:
        raw = cipher.decrypt(token.encode("utf-8")).decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        raise ValueError("no se pudo descifrar mcp_config")


def _decrypt_env_vars(value: Any) -> dict[str, str]:
    if isinstance(value, dict) and value.get(ENCRYPTED_FLAG) is True:
        try:
            return _decrypt_payload(value)
        except ValueError:
            # If decryption fails (e.g. missing key), return empty to prevent crash
            return {}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {}


def _mask_env_vars(env_vars: dict[str, str]) -> dict[str, str]:
    return {key: "__masked__" for key in env_vars.keys()}


def _paths() -> dict[str, str]:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return {
        "registry": os.path.join(root, "app/data/mcp_registry.json"),
        "legacy_config": os.path.join(root, "app/settings/active_mcp.json"),
    }


def _load_json(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def get_registry_custom() -> dict[str, Any]:
    data = get_app_setting(REGISTRY_KEY)
    if isinstance(data, dict):
        return data
    return {}


def set_registry_custom(registry: dict[str, Any]) -> None:
    if not isinstance(registry, dict):
        raise ValueError("registry inválido")
    set_app_setting(REGISTRY_KEY, registry)


def get_registry_sources() -> dict[str, Any]:
    data = get_app_setting(SOURCES_KEY)
    if isinstance(data, dict):
        return data
    return {"sources": []}


def set_registry_sources(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload inválido")
    set_app_setting(SOURCES_KEY, payload)


def get_registry_merged() -> dict[str, Any]:
    paths = _paths()
    registry = _load_json(paths["registry"])
    custom = get_registry_custom()
    merged = {**registry, **custom}
    for key, value in merged.items():
        if isinstance(value, dict) and "source" not in value:
            value["source"] = "built-in" if key in registry else "custom"
    return merged


def _legacy_to_config() -> dict[str, Any]:
    paths = _paths()
    legacy = _load_json(paths["legacy_config"])
    if not isinstance(legacy, dict) or not legacy:
        return {"servers": {}}
    return {"servers": legacy}


def _merge_legacy_config(current: dict[str, Any], legacy: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not isinstance(current, dict) or "servers" not in current:
        current = {"servers": {}}
    legacy_servers = legacy.get("servers", {}) if isinstance(legacy, dict) else {}
    servers = current.get("servers", {})
    updated = False
    for server_id, legacy_settings in legacy_servers.items():
        if not isinstance(legacy_settings, dict):
            continue
        existing = servers.get(server_id)
        if not isinstance(existing, dict):
            new_entry = dict(legacy_settings)
            env_vars = legacy_settings.get("env_vars")
            if isinstance(env_vars, dict) and not env_vars.get(ENCRYPTED_FLAG):
                new_entry["env_vars"] = _encrypt_payload(env_vars)
            servers[server_id] = new_entry
            updated = True
            continue
        if "enabled" not in existing and "enabled" in legacy_settings:
            existing["enabled"] = legacy_settings.get("enabled")
            updated = True
        if not existing.get("params") and legacy_settings.get("params"):
            existing["params"] = legacy_settings.get("params")
            updated = True
        env_vars = legacy_settings.get("env_vars")
        existing_env = existing.get("env_vars")
        if isinstance(existing_env, dict) and not existing_env.get(ENCRYPTED_FLAG) and isinstance(env_vars, dict):
            safe_keys = {"JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_TYPE"}
            for key in safe_keys:
                legacy_value = env_vars.get(key)
                if legacy_value and legacy_value != existing_env.get(key):
                    existing_env[key] = legacy_value
                    updated = True
            existing["env_vars"] = existing_env
        if isinstance(env_vars, dict) and not env_vars.get(ENCRYPTED_FLAG):
            env_vars = _encrypt_payload(env_vars)
        if env_vars and (existing_env is None or (isinstance(existing_env, dict) and not existing_env)):
            existing["env_vars"] = env_vars
            updated = True
        servers[server_id] = existing
    current["servers"] = servers
    return current, updated


def get_active_config() -> dict[str, Any]:
    data = get_app_setting(CONFIG_KEY)
    if isinstance(data, dict) and "servers" in data:
        legacy = _legacy_to_config()
        merged, updated = _merge_legacy_config(data, legacy)
        if updated:
            set_app_setting(CONFIG_KEY, merged)
        return merged
    legacy = _legacy_to_config()
    if legacy.get("servers"):
        merged, _ = _merge_legacy_config({"servers": {}}, legacy)
        set_app_setting(CONFIG_KEY, merged)
    return legacy


def get_active_config_runtime() -> dict[str, Any]:
    config = get_active_config()
    servers = {}
    for server_id, settings in config.get("servers", {}).items():
        env_vars = _decrypt_env_vars(settings.get("env_vars"))
        servers[server_id] = {
            "enabled": bool(settings.get("enabled", False)),
            "params": settings.get("params", {}) or {},
            "env_vars": env_vars,
        }
        if "command" in settings:
            servers[server_id]["command"] = settings.get("command")
        if "args" in settings:
            servers[server_id]["args"] = settings.get("args")
    return {"servers": servers}


def get_active_config_public() -> dict[str, Any]:
    config = get_active_config()
    servers = {}
    for server_id, settings in config.get("servers", {}).items():
        env_vars = _decrypt_env_vars(settings.get("env_vars"))
        servers[server_id] = {
            "enabled": bool(settings.get("enabled", False)),
            "params": settings.get("params", {}) or {},
            "env_vars": _mask_env_vars(env_vars),
        }
    return {"servers": servers}


def upsert_server_config(server_id: str, settings: dict[str, Any], keep_masked: bool = True) -> None:
    if not server_id:
        raise ValueError("server_id vacío")
    config = get_active_config()
    servers = config.get("servers", {})
    existing = servers.get(server_id, {})
    incoming_env_vars = settings.get("env_vars", {}) or {}
    existing_env_vars = _decrypt_env_vars(existing.get("env_vars"))
    merged_env_vars = dict(existing_env_vars)
    for key, value in incoming_env_vars.items():
        if keep_masked and (value == "__masked__" or value == ""):
            continue
        merged_env_vars[str(key)] = str(value)
    if merged_env_vars and _get_cipher() is None:
        # Warn but allow if encryption is not configured (dev mode)
        pass
    servers[server_id] = {
        "enabled": bool(settings.get("enabled", True)),
        "params": settings.get("params", {}) or {},
        "env_vars": _encrypt_payload(merged_env_vars),
    }
    if "command" in settings:
        servers[server_id]["command"] = settings.get("command")
    if "args" in settings:
        servers[server_id]["args"] = settings.get("args")
    config["servers"] = servers
    set_app_setting(CONFIG_KEY, config)


def delete_server_config(server_id: str) -> bool:
    config = get_active_config()
    servers = config.get("servers", {})
    if server_id in servers:
        del servers[server_id]
        config["servers"] = servers
        set_app_setting(CONFIG_KEY, config)
        return True
    return False


def update_registry_entry(server_id: str, definition: dict[str, Any]) -> None:
    registry = get_registry_custom()
    definition = dict(definition)
    definition["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    registry[server_id] = definition
    set_registry_custom(registry)


def delete_registry_entry(server_id: str) -> bool:
    registry = get_registry_custom()
    if server_id in registry:
        del registry[server_id]
        set_registry_custom(registry)
        return True
    return False
