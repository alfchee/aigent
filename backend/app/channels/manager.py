import asyncio
import importlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.channels.base import BaseChannel
from app.channels.config import get_channels_config, upsert_channel_config
from app.channels.events import publish
from app.channels.registry import ChannelRegistry
from app.channels.telegram import TelegramChannel
from app.core.persistence import get_app_setting, set_app_setting


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class ChannelStatus:
    channel_id: str
    state: str
    last_heartbeat: str | None = None
    last_error: str | None = None
    started_at: str | None = None
    event_rate: float = 0.0
    _window_started_at: float = field(default_factory=lambda: 0.0)
    _event_count: int = 0

    def touch(self) -> None:
        now = datetime.now(tz=timezone.utc)
        now_ts = now.timestamp()
        if self._window_started_at == 0.0 or now_ts - self._window_started_at > 60:
            self._window_started_at = now_ts
            self._event_count = 0
        self._event_count += 1
        window = max(1.0, now_ts - self._window_started_at)
        self.event_rate = round(self._event_count / window, 4)
        self.last_heartbeat = now.isoformat()


class ChannelManager:
    def __init__(self):
        self.registry = ChannelRegistry()
        self.registry.register(TelegramChannel)
        self.active_channels: dict[str, BaseChannel] = {}
        self.statuses: dict[str, ChannelStatus] = {}
        self._lock = asyncio.Lock()

    def list_specs(self) -> list[dict[str, Any]]:
        self._load_registry_modules()
        specs = []
        for spec in self.registry.list_specs():
            specs.append(
                {
                    "channel_id": spec.channel_id,
                    "display_name": spec.display_name,
                    "version": spec.version,
                    "capabilities": spec.capabilities,
                    "supports_polling": spec.supports_polling,
                    "supports_webhook": spec.supports_webhook,
                    "settings_schema": spec.settings_schema,
                }
            )
        return specs

    def get_status(self, channel_id: str) -> ChannelStatus | None:
        return self.statuses.get(channel_id)

    def list_statuses(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for status in self.statuses.values():
            items.append(
                {
                    "channel_id": status.channel_id,
                    "state": status.state,
                    "last_heartbeat": status.last_heartbeat,
                    "last_error": status.last_error,
                    "started_at": status.started_at,
                    "event_rate": status.event_rate,
                }
            )
        return items

    def _set_status(self, channel_id: str, state: str, error: str | None = None) -> None:
        status = self.statuses.get(channel_id)
        if status is None:
            status = ChannelStatus(channel_id=channel_id, state=state)
            self.statuses[channel_id] = status
        status.state = state
        if state == "active" and status.started_at is None:
            status.started_at = _utc_now_iso()
        if error:
            status.last_error = error
        publish("channels", "status", self._status_payload(status))
        self._record_status(status)

    def _status_payload(self, status: ChannelStatus) -> dict[str, Any]:
        return {
            "channel_id": status.channel_id,
            "state": status.state,
            "last_heartbeat": status.last_heartbeat,
            "last_error": status.last_error,
            "started_at": status.started_at,
            "event_rate": status.event_rate,
            "timestamp": _utc_now_iso(),
        }

    async def _status_callback(self, channel_id: str, event_type: str, data: dict[str, Any]) -> None:
        status = self.statuses.get(channel_id)
        if status is None:
            status = ChannelStatus(channel_id=channel_id, state="active")
            self.statuses[channel_id] = status
        if event_type == "heartbeat":
            status.touch()
            publish("channels", "heartbeat", self._status_payload(status))
            self._record_status(status)
        elif event_type == "error":
            message = data.get("message") if isinstance(data, dict) else None
            status.last_error = message
            self._set_status(channel_id, "error", message)

    def _record_status(self, status: ChannelStatus) -> None:
        history = get_app_setting("channels_status_history")
        if not isinstance(history, list):
            history = []
        history.append(self._status_payload(status))
        history = history[-200:]
        set_app_setting("channels_status_history", history)

    async def load_from_settings(self) -> None:
        self._load_registry_modules()
        cfg = get_channels_config()
        channels = cfg.get("channels")
        if not isinstance(channels, dict):
            return
        for channel_id, entry in channels.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("enabled") is True:
                await self.enable_channel(channel_id, entry.get("settings") or {}, persist=False)

    def _load_registry_modules(self) -> None:
        cfg = get_channels_config()
        modules = cfg.get("registry_modules") if isinstance(cfg, dict) else None
        if not isinstance(modules, list):
            return
        for module_path in modules:
            if not isinstance(module_path, str) or not module_path.strip():
                continue
            try:
                module = importlib.import_module(module_path)
            except Exception:
                continue
            channel_class = getattr(module, "Channel", None) or getattr(module, "channel_class", None)
            if channel_class and isinstance(channel_class, type) and issubclass(channel_class, BaseChannel):
                self.registry.register(channel_class)

    async def validate_channel(self, channel_id: str, settings: dict[str, Any], check_connection: bool = False) -> list[str]:
        spec = self.registry.get_spec(channel_id)
        if spec is None:
            return ["channel desconocido"]
        return await spec.channel_class.validate_settings(settings, check_connection=check_connection)

    async def enable_channel(self, channel_id: str, settings: dict[str, Any], persist: bool = True) -> dict[str, Any]:
        spec = self.registry.get_spec(channel_id)
        if spec is None:
            raise ValueError("channel desconocido")
        errors = await self.validate_channel(channel_id, settings, check_connection=True)
        if errors:
            return {"status": "error", "errors": errors}
        async with self._lock:
            if channel_id in self.active_channels:
                return {"status": "active", "channel_id": channel_id}
            channel = spec.channel_class(settings=settings, status_callback=lambda event, data: self._status_callback(channel_id, event, data))
            self.active_channels[channel_id] = channel
            self._set_status(channel_id, "starting")
            try:
                await channel.start()
                self._set_status(channel_id, "active")
            except Exception as e:
                self._set_status(channel_id, "error", str(e))
                raise
        if persist:
            upsert_channel_config(channel_id, {"enabled": True, "settings": settings})
        return {"status": "active", "channel_id": channel_id}

    async def disable_channel(self, channel_id: str, persist: bool = True) -> dict[str, Any]:
        async with self._lock:
            channel = self.active_channels.get(channel_id)
            if channel is None:
                self._set_status(channel_id, "disabled")
                if persist:
                    upsert_channel_config(channel_id, {"enabled": False, "settings": {}})
                return {"status": "disabled", "channel_id": channel_id}
            try:
                await channel.stop()
            finally:
                self.active_channels.pop(channel_id, None)
                self._set_status(channel_id, "disabled")
        if persist:
            upsert_channel_config(channel_id, {"enabled": False, "settings": {}})
        return {"status": "disabled", "channel_id": channel_id}

    async def send_message(self, channel_id: str, recipient_id: str, message: str) -> None:
        channel = self.active_channels.get(channel_id)
        if channel is None:
            raise ValueError("channel no activo")
        await channel.send_message(recipient_id, message)

    async def start_all(self) -> None:
        await self.load_from_settings()

    async def stop_all(self) -> None:
        tasks = [self.disable_channel(channel_id, persist=False) for channel_id in list(self.active_channels.keys())]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


channel_manager = ChannelManager()
