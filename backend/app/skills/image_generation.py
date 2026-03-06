import base64
import json
import os
import logging
from datetime import datetime, timezone

from app.core.filesystem import SessionWorkspace
from app.core.runtime_context import emit_event, get_session_id

logger = logging.getLogger(__name__)

def _extension_for_mime(mime_type: str | None) -> str:
    if not mime_type:
        return "png"
    if "png" in mime_type:
        return "png"
    if "jpeg" in mime_type or "jpg" in mime_type:
        return "jpg"
    if "webp" in mime_type:
        return "webp"
    return "png"


async def generate_image(prompt: str, aspect_ratio: str | None = None, file_name: str | None = None, **kwargs) -> str:
    """
    Generates an image from a prompt and saves it to the session workspace.
    """
    # Ignorar argumentos extra como 'model' que el agente pueda enviar
    if kwargs:
        logger.info(f"generate_image received extra args: {kwargs.keys()}")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Error: GOOGLE_API_KEY no configurado."

    prompt = (prompt or "").strip()
    if not prompt:
        return "Error: prompt vacío."

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    if aspect_ratio:
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )
    else:
        config = types.GenerateContentConfig(response_modalities=["IMAGE"])

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=config,
        )
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return f"Error generando imagen: {str(e)}"

    parts = []
    if getattr(response, "candidates", None):
        candidate = response.candidates[0]
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) if content else []
    elif getattr(response, "parts", None):
        parts = response.parts

    image_data = None
    mime_type = None
    for part in parts:
        inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        if inline:
            image_data = getattr(inline, "data", None)
            mime_type = getattr(inline, "mime_type", None) or getattr(inline, "mimeType", None)
            if image_data:
                break

    if not image_data:
        return "Error: no se obtuvo imagen."

    # Debugging image data type
    logger.info(f"Image data type: {type(image_data)}")
    if isinstance(image_data, (bytes, bytearray)):
        logger.info(f"Image data preview (bytes): {image_data[:20]!r}")
    elif isinstance(image_data, str):
        logger.info(f"Image data preview (str): {image_data[:20]!r}")

    # Handle decoding based on type and content
    image_bytes = None
    
    if isinstance(image_data, bytes):
        # Check for common image headers
        # PNG: 89 50 4E 47 0D 0A 1A 0A
        # JPEG: FF D8 FF
        # WebP: RIFF...WEBP
        if image_data.startswith(b'\x89PNG') or image_data.startswith(b'\xff\xd8') or (image_data.startswith(b'RIFF') and b'WEBP' in image_data[:16]):
            logger.info("Detected raw image bytes. Skipping base64 decoding.")
            image_bytes = image_data
        else:
            # Try decoding assuming it's base64 bytes
            try:
                image_bytes = base64.b64decode(image_data)
                logger.info("Successfully decoded base64 bytes.")
            except Exception as e:
                logger.warning(f"Failed to decode base64 bytes, assuming raw: {e}")
                image_bytes = image_data
    elif isinstance(image_data, str):
        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            return f"Error decodificando base64 string: {e}"
    else:
        return f"Error: tipo de datos de imagen no soportado ({type(image_data)})"

    session_id = get_session_id()
    ws = SessionWorkspace(session_id)
    ext = _extension_for_mime(mime_type)
    name = (file_name or "").strip()
    if not name:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = f"generated/images/image_{stamp}.{ext}"
    elif "." not in name:
        name = f"{name}.{ext}"

    meta = ws.write_bytes(name, image_bytes)
    emit_event("artifact", {"session_id": session_id, "op": "write", "path": meta.get("path"), "meta": meta})
    url = f"/api/workspace/{session_id}/files/{meta['path']}"
    return json.dumps(
        {
            "session_id": session_id,
            "path": meta["path"],
            "mime_type": meta["mime_type"],
            "size_bytes": meta["size_bytes"],
            "url": url,
        },
        ensure_ascii=False,
    )


tools = [generate_image]
