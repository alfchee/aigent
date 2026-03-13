from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends
from typing import Optional
import logging
import json
import asyncio
import uuid
import time

from app.core.ws_manager import manager
from app.core.agent import NaviBot
from app.core.runtime_context import set_session_id, reset_session_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/api/ws/chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for real-time chat.
    client_id: Unique identifier for the client connection (e.g. UUID).
    token: Authentication token (optional for now, can be session_id).
    """
    # Verify session/token logic here
    # For now, we assume client_id is the session_id or a valid identifier
    session_id = client_id 
    
    # Accept connection
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Wait for message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            msg_type = message_data.get("type")
            
            if msg_type == "ping":
                await manager.send_json({"type": "pong"}, client_id)
                continue
                
            if msg_type == "chat.message":
                user_content = message_data.get("content", "")
                msg_id = message_data.get("id", str(uuid.uuid4()))
                
                # Acknowledge receipt
                # await manager.send_json({"type": "ack", "id": msg_id}, client_id)
                
                # Execute Agent Logic
                # We need to run this in a way that doesn't block the WebSocket loop if we want to support "stop" messages
                # But for V1, sequential processing is acceptable.
                
                # Set context
                token_ctx = set_session_id(session_id)
                
                try:
                    # Initialize bot
                    bot = NaviBot()
                    
                    # Define callback for streaming events
                    async def event_callback(event_type: str, data: dict):
                        await manager.send_json({
                            "type": f"agent.{event_type}",
                            "data": data
                        }, client_id)

                    # Stream response
                    # Note: We need to implement stream_chat in NaviBot
                    await bot.stream_chat(
                        message=user_content,
                        session_id=session_id,
                        callback=event_callback
                    )
                    
                    # Final response is sent by stream_chat via callback usually, 
                    # or we can send a "done" message here.
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    await manager.send_json({
                        "type": "error",
                        "code": "agent_error",
                        "message": str(e)
                    }, client_id)
                finally:
                    reset_session_id(token_ctx)
            
            elif msg_type == "chat.stop":
                # Handle stop request (requires task cancellation logic)
                pass

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(client_id)
