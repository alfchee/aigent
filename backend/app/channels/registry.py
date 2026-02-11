from dataclasses import dataclass
from typing import Any, Type

from app.channels.base import BaseChannel


@dataclass
class ChannelSpec:
    channel_id: str
    display_name: str
    version: str
    capabilities: list[str]
    supports_polling: bool
    supports_webhook: bool
    settings_schema: dict[str, Any]
    channel_class: Type[BaseChannel]


class ChannelRegistry:
    def __init__(self):
        self._registry: dict[str, ChannelSpec] = {}

    def register(self, channel_class: Type[BaseChannel]) -> None:
        channel_id = channel_class.channel_id()
        spec = ChannelSpec(
            channel_id=channel_id,
            display_name=channel_class.display_name(),
            version=channel_class.version(),
            capabilities=channel_class.capabilities(),
            supports_polling=channel_class.supports_polling(),
            supports_webhook=channel_class.supports_webhook(),
            settings_schema=channel_class.settings_schema(),
            channel_class=channel_class,
        )
        self._registry[channel_id] = spec

    def list_specs(self) -> list[ChannelSpec]:
        return list(self._registry.values())

    def get_spec(self, channel_id: str) -> ChannelSpec | None:
        return self._registry.get(channel_id)
