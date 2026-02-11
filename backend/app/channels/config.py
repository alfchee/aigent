from typing import Any

from app.core.persistence import get_app_setting, set_app_setting


CONFIG_KEY = "channels_config"


def get_channels_config() -> dict[str, Any]:
    data = get_app_setting(CONFIG_KEY)
    if isinstance(data, dict):
        return data
    return {"channels": {}}


def set_channels_config(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload inválido")
    set_app_setting(CONFIG_KEY, payload)


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
