from app.channels.config import get_channel_config
from app.channels.manager import channel_manager


async def send_telegram_message(recipient_id: str, message: str) -> str:
    """
    Sends a message to a Telegram user.
    
    Args:
        recipient_id: Telegram user ID.
        message: The message to send.
        
    Returns:
        String indicating the result.
    """
    if not isinstance(recipient_id, str) or not recipient_id.strip():
        return "recipient_id required"
    if not isinstance(message, str) or not message.strip():
        return "message required"
    channel = channel_manager.active_channels.get("telegram")
    if channel is None:
        entry = get_channel_config("telegram")
        if isinstance(entry, dict) and entry.get("enabled") is True:
            result = await channel_manager.enable_channel("telegram", entry.get("settings") or {}, persist=False)
            if isinstance(result, dict) and result.get("status") != "active":
                return "Could not activate Telegram channel"
            channel = channel_manager.active_channels.get("telegram")
        else:
            return "Telegram channel is not active. Enable it in Channels with the token."
    await channel.send_message(recipient_id, message)
    return "Message sent to Telegram"


tools = [send_telegram_message]
