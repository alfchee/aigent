import json
import os
from typing import Any

from app.core.persistence import get_app_setting, set_app_setting


CONFIG_KEY = "channels_config"
ENCRYPTED_FLAG = "__encrypted__"


def _get_cipher():
    key = os.getenv("NAVIBOT_CHANNELS_ENCRYPTION_KEY") or os.getenv("NAVIBOT_CHANNELS_KEY")
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


def _decrypt_payload(data: dict[str, Any]) -> dict[str, Any]:
    cipher = _get_cipher()
    if cipher is None:
        raise ValueError("clave de cifrado requerida para channels_config")
    token = data.get("ciphertext")
    if not isinstance(token, str) or not token:
        return {"channels": {}}
    try:
        raw = cipher.decrypt(token.encode("utf-8")).decode("utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {"channels": {}}
    except Exception:
        raise ValueError("no se pudo descifrar channels_config")


def get_channels_config() -> dict[str, Any]:
    data = get_app_setting(CONFIG_KEY)
    if isinstance(data, dict) and data.get(ENCRYPTED_FLAG) is True:
        return _decrypt_payload(data)
    if isinstance(data, dict):
        return data
    return {"channels": {}}


def set_channels_config(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload inválido")
    encrypted = _encrypt_payload(payload)
    set_app_setting(CONFIG_KEY, encrypted)


def get_channel_config(channel_id: str) -> dict[str, Any]:
    cfg = get_channels_config()
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        return {}
    entry = channels.get(channel_id)
    if isinstance(entry, dict):
        return entry
    return {}


def upsert_channel_config(channel_id: str, entry: dict[str, Any]) -> None:
    cfg = get_channels_config()
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    channels[channel_id] = entry
    cfg["channels"] = channels
    set_channels_config(cfg)
