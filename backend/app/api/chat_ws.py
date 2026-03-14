from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional
import logging
import json
import asyncio
import uuid
import os
import hashlib
import hmac

from app.core.ws_manager import manager
from app.core.agent import NaviBot
from app.core.runtime_context import set_session_id, reset_session_id

router = APIRouter()
logger = logging.getLogger(__name__)


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

    async def run_agent_message(user_content: str, msg_id: str):
        token_ctx = set_session_id(session_id)
        try:
            bot = NaviBot()

            async def event_callback(event_type: str, data: dict):
                await manager.send_json({"type": f"agent.{event_type}", "data": data}, client_id)

            await bot.stream_chat(message=user_content, session_id=session_id, callback=event_callback)
        except asyncio.CancelledError:
            await manager.send_json(
                {
                    "type": "agent.response",
                    "data": {"content": "", "done": True, "cancelled": True, "id": msg_id},
                },
                client_id,
            )
            raise
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await manager.send_json(
                {
                    "type": "error",
                    "code": "agent_error",
                    "message": str(e),
                },
                client_id,
            )
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
                user_content = message_data.get("content", "")
                msg_id = message_data.get("id", str(uuid.uuid4()))

                if running_task and not running_task.done():
                    running_task.cancel()
                    try:
                        await running_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

                running_task = asyncio.create_task(run_agent_message(user_content, msg_id))
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
