from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable


class BaseChannel(ABC):
    def __init__(self, settings: dict[str, Any], status_callback: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None):
        self.settings = settings or {}
        self._status_callback = status_callback

    @classmethod
    @abstractmethod
    def channel_id(cls) -> str:
        raise NotImplementedError

    @classmethod
    def display_name(cls) -> str:
        return cls.channel_id()

    @classmethod
    def version(cls) -> str:
        return "1.0.0"

    @classmethod
    def capabilities(cls) -> list[str]:
        return []

    @classmethod
    def supports_polling(cls) -> bool:
        return False

    @classmethod
    def supports_webhook(cls) -> bool:
        return False

    @classmethod
    def settings_schema(cls) -> dict[str, Any]:
        return {}

    @classmethod
    async def validate_settings(cls, settings: dict[str, Any], check_connection: bool = False) -> list[str]:
        return []

    async def _heartbeat(self) -> None:
        if self._status_callback:
            await self._status_callback("heartbeat", {})

    async def _error(self, message: str) -> None:
        if self._status_callback:
            await self._status_callback("error", {"message": message})

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, recipient_id: str, message: str) -> None:
        raise NotImplementedError
