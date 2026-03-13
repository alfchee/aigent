from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json
import asyncio
import uuid

from app.core.ws_manager import manager
from app.core.agent import NaviBot
from app.core.runtime_context import set_session_id, reset_session_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/api/ws/chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: Optional[str] = Query(None)):
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
