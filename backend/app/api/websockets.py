import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger("navibot.api.websockets")

class ConnectionManager:
    """
    Manages active WebSocket connections.
    Supports broadcasting and targeted messaging.
    """
    def __init__(self):
        # Map session_id -> List of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        logger.info(f"WebSocket connected: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            try:
                self.active_connections[session_id].remove(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
            except ValueError:
                pass
        logger.info(f"WebSocket disconnected: {session_id}")

    async def send_message(self, message: str, session_id: str):
        """Send text message to all clients in a session."""
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")

    async def send_json(self, data: Dict[str, Any], session_id: str):
        """Send JSON payload to all clients in a session."""
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending JSON: {e}")

manager = ConnectionManager()
