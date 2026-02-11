from typing import Any

from app.channels.base import BaseChannel


class WebhookTemplateChannel(BaseChannel):
    @classmethod
    def channel_id(cls) -> str:
        return "template_webhook"

    @classmethod
    def display_name(cls) -> str:
        return "Template Webhook"

    @classmethod
    def capabilities(cls) -> list[str]:
        return []

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
