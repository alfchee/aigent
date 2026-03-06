from typing import Any

from app.channels.base import BaseChannel


class HybridTemplateChannel(BaseChannel):
    @classmethod
    def channel_id(cls) -> str:
        return "template_hybrid"

    @classmethod
    def display_name(cls) -> str:
        return "Template Hybrid"

    @classmethod
    def capabilities(cls) -> list[str]:
        return []

    @classmethod
    def supports_polling(cls) -> bool:
        return True

    @classmethod
    def supports_webhook(cls) -> bool:
        return True

    @classmethod
    def settings_schema(cls) -> dict[str, Any]:
        return {"fields": []}

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def send_message(self, recipient_id: str, message: str) -> None:
        raise NotImplementedError
