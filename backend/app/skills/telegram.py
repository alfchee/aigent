from app.channels.config import get_channel_config
from app.channels.manager import channel_manager


async def send_telegram_message(recipient_id: str, message: str) -> str:
    """
    Envía un mensaje a un usuario de Telegram.
    
    Args:
        recipient_id: ID del usuario de Telegram.
        message: El mensaje a enviar.
        
    Returns:
        String indicando el resultado.
    """
    if not isinstance(recipient_id, str) or not recipient_id.strip():
        return "recipient_id requerido"
    if not isinstance(message, str) or not message.strip():
        return "message requerido"
    channel = channel_manager.active_channels.get("telegram")
    if channel is None:
        entry = get_channel_config("telegram")
        if isinstance(entry, dict) and entry.get("enabled") is True:
            result = await channel_manager.enable_channel("telegram", entry.get("settings") or {}, persist=False)
            if isinstance(result, dict) and result.get("status") != "active":
                return "No se pudo activar el canal Telegram"
            channel = channel_manager.active_channels.get("telegram")
        else:
            return "Canal Telegram no está activo. Actívalo en Channels con el token."
    await channel.send_message(recipient_id, message)
    return "Mensaje enviado a Telegram"


tools = [send_telegram_message]
