from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional
import logging
import json
import asyncio
import uuid
import os
import hashlib
import hmac
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ValidationError
from typing import Literal

from app.core.ws_manager import manager
from app.core.agent import NaviBot
from app.core.runtime_context import set_session_id, reset_session_id

router = APIRouter()
logger = logging.getLogger(__name__)

# Error codes for specific error types
ERROR_CODES = {
    "invalid_api_key": "API key inválida o no configurada",
    "model_not_available": "Modelo no encontrado o no disponible",
    "rate_limit": "Límite de requests excedido",
    "tool_error": "Error al ejecutar herramienta",
    "agent_error": "Error general del agente",
    "timeout": "Timeout de ejecución",
    "connection_error": "Error de conexión",
    "validation_error": "Error de validación",
}

# Valid model providers
VALID_PROVIDERS = Literal["google", "openrouter", "lm_studio"]


class ChatMessageRequest(BaseModel):
    """Pydantic model for validating WebSocket chat messages."""
    model_provider: Optional[VALID_PROVIDERS] = None
    content: str = Field(..., min_length=1)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[int] = None


class ChatInitRequest(BaseModel):
    """Pydantic model for validating WebSocket initialization message."""
    model_provider: Optional[VALID_PROVIDERS] = None
    model_name: Optional[str] = None


def _classify_error(error: Exception) -> tuple[str, str]:
    """Classify error and return code and message."""
    error_str = str(error).lower()
    
    # Check for API key errors
    if "api key" in error_str or "auth" in error_str or "unauthorized" in error_str:
        return ("invalid_api_key", str(error))
    
    # Check for model not available
    if "model" in error_str and ("not found" in error_str or "not available" in error_str or "does not exist" in error_str):
        return ("model_not_available", str(error))
    
    # Check for rate limit
    if "rate limit" in error_str or "too many requests" in error_str:
        return ("rate_limit", str(error))
    
    # Check for timeout
    if "timeout" in error_str or "timed out" in error_str:
        return ("timeout", str(error))
    
    # Check for tool errors
    if "tool" in error_str:
        return ("tool_error", str(error))
    
    # Default to agent error
    return ("agent_error", str(error))


async def _send_structured_message(websocket, client_id: str, msg_type: str, payload: Dict[str, Any]):
    """Send a structured JSON message to the client."""
    message = {
        "type": msg_type,
        "payload": payload
    }
    try:
        await websocket.send_json(message)
    except Exception as e:
        logger.error(f"Error sending message to {client_id}: {e}")


async def _send_error(websocket, client_id: str, error: Exception):
    """Send a structured error message to the client."""
    code, message = _classify_error(error)
    error_payload = {
        "code": code,
        "message": message,
        "description": ERROR_CODES.get(code, "Error desconocido")
    }
    await _send_structured_message(websocket, client_id, "error", error_payload)


def _validate_ws_token(token: Optional[str], client_id: str) -> bool:
    """Validate WebSocket token using HMAC signature."""
    # If no token required (development mode), allow all
    if not os.getenv("WS_AUTH_REQUIRED", "false").lower() in ("true", "1", "yes"):
        return True
    
    # Token is required
    if not token:
        return False
    
    # Validate HMAC token format: signature:timestamp
    expected_secret = os.getenv("WS_SECRET_KEY", "")
    if not expected_secret:
        logger.warning("WS_SECRET_KEY not set, rejecting all tokens")
        return False
    
    try:
        sig_part, timestamp_part = token.split(":")
        timestamp = int(timestamp_part)
        # Check if token is not expired (24 hours)
        if abs(time.time() - timestamp) > 86400:
            return False
        # Verify HMAC
        message = f"{client_id}:{timestamp}"
        expected_sig = hmac.new(
            expected_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig_part, expected_sig)
    except (ValueError, TypeError):
        return False


import time

@router.websocket("/api/ws/chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: Optional[str] = Query(None)):
    # Validate token before accepting connection
    if not _validate_ws_token(token, client_id):
        await websocket.close(code=4003, reason="Unauthorized")
        return
    
    session_id = client_id
    await manager.connect(websocket, client_id)

    running_task: Optional[asyncio.Task] = None
    current_provider: Optional[str] = None

    async def run_agent_message(user_content: str, msg_id: str, provider: Optional[str] = None):
        token_ctx = set_session_id(session_id)
        try:
            bot = NaviBot(provider=provider)
            stream_state = {
                "has_error": False,
                "has_visible_output": False,
            }

            async def event_callback(event_type: str, data: dict):
                if event_type == "error":
                    stream_state["has_error"] = True
                elif event_type == "token":
                    content = str(data.get("content", "") or "")
                    if content.strip():
                        stream_state["has_visible_output"] = True
                elif event_type == "response":
                    content = str(data.get("content", "") or "")
                    if content.strip():
                        stream_state["has_visible_output"] = True
                await manager.send_json({"type": f"agent.{event_type}", "data": data}, client_id)

            stream_timeout = int(os.getenv("NAVIBOT_STREAM_TIMEOUT_SECONDS", "240"))
            await asyncio.wait_for(
                bot.stream_chat(message=user_content, session_id=session_id, callback=event_callback),
                timeout=stream_timeout
            )
            
            if stream_state["has_error"]:
                logger.warning(f"Stream ended with error for session={session_id} msg_id={msg_id}")
                await manager.send_json({"type": "done", "data": {"id": msg_id, "error": True}}, client_id)
            elif not stream_state["has_visible_output"]:
                logger.warning(f"Stream ended without visible output for session={session_id} msg_id={msg_id}")
                await manager.send_json(
                    {
                        "type": "error",
                        "code": "empty_response",
                        "message": "El agente terminó sin generar respuesta visible.",
                        "description": "El flujo terminó sin tokens ni contenido final.",
                    },
                    client_id,
                )
                await manager.send_json({"type": "done", "data": {"id": msg_id, "error": True}}, client_id)
            else:
                logger.info(f"Stream completed successfully for session={session_id} msg_id={msg_id}")
                await manager.send_json({"type": "done", "data": {"id": msg_id}}, client_id)
            
        except asyncio.CancelledError:
            await manager.send_json(
                {
                    "type": "agent.response",
                    "data": {"content": "", "done": True, "cancelled": True, "id": msg_id},
                },
                client_id,
            )
            # Send done message for cancelled state
            await manager.send_json({"type": "done", "data": {"id": msg_id, "cancelled": True}}, client_id)
            raise
        except asyncio.TimeoutError:
            logger.error(f"Timeout processing message for session={session_id} msg_id={msg_id}", exc_info=True)
            await manager.send_json(
                {
                    "type": "error",
                    "code": "timeout",
                    "message": "La generación excedió el tiempo máximo permitido.",
                    "description": ERROR_CODES.get("timeout", "Timeout de ejecución"),
                },
                client_id,
            )
            await manager.send_json({"type": "done", "data": {"id": msg_id, "error": True}}, client_id)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Use structured error message
            code, message = _classify_error(e)
            await manager.send_json(
                {
                    "type": "error",
                    "code": code,
                    "message": message,
                    "description": ERROR_CODES.get(code, "Error desconocido"),
                },
                client_id,
            )
            # Send done message after error
            await manager.send_json({"type": "done", "data": {"id": msg_id, "error": True}}, client_id)
        finally:
            reset_session_id(token_ctx)

    def consume_task_result(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unhandled chat task error")

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            msg_type = message_data.get("type")

            if msg_type == "ping":
                await manager.send_json({"type": "pong"}, client_id)
                continue

            if msg_type == "chat.message":
                # Validate message using Pydantic
                try:
                    validated_msg = ChatMessageRequest(**message_data)
                except ValidationError as e:
                    # Send validation error and close connection
                    error_details = e.errors()
                    error_msg = "; ".join([f"{err['loc']}: {err['msg']}" for err in error_details])
                    await manager.send_json({
                        "type": "error",
                        "code": "validation_error",
                        "message": "Invalid message format",
                        "description": error_msg,
                    }, client_id)
                    await manager.send_json({"type": "done", "data": {"id": message_data.get("id", "unknown"), "error": True}}, client_id)
                    continue
                
                user_content = validated_msg.content
                msg_id = validated_msg.id
                provider = validated_msg.model_provider
                
                # Update current provider if provided
                if provider:
                    current_provider = provider

                if running_task and not running_task.done():
                    running_task.cancel()
                    try:
                        await running_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

                running_task = asyncio.create_task(run_agent_message(user_content, msg_id, current_provider))
                running_task.add_done_callback(consume_task_result)
                continue

            if msg_type == "chat.stop":
                if running_task and not running_task.done():
                    running_task.cancel()
                    try:
                        await running_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass
                else:
                    await manager.send_json(
                        {
                            "type": "agent.response",
                            "data": {"content": "", "done": True, "cancelled": True},
                        },
                        client_id,
                    )
                continue

    except WebSocketDisconnect:
        if running_task and not running_task.done():
            running_task.cancel()
            try:
                await running_task
            except Exception:
                pass
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        if running_task and not running_task.done():
            running_task.cancel()
            try:
                await running_task
            except Exception:
                pass
        manager.disconnect(client_id)
