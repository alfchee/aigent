import logging
from typing import Any, Dict, List
from fastapi import WebSocket

logger = logging.getLogger("navibot.api.websockets")

class ConnectionManager:
    def __init__(self):
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

    def _session_connections(self, session_id: str) -> List[WebSocket]:
        return list(self.active_connections.get(session_id, []))

    def _cleanup_stale(self, session_id: str, stale: List[WebSocket]) -> None:
        if not stale:
            return
        for conn in stale:
            self.disconnect(conn, session_id)

    async def send_message(self, message: str, session_id: str):
        stale: List[WebSocket] = []
        for connection in self._session_connections(session_id):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error("Error sending message: %s", e)
                stale.append(connection)
        self._cleanup_stale(session_id, stale)

    async def send_json(self, data: Dict[str, Any], session_id: str):
        stale: List[WebSocket] = []
        for connection in self._session_connections(session_id):
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error("Error sending JSON: %s", e)
                stale.append(connection)
        self._cleanup_stale(session_id, stale)

    def active_count(self, session_id: str) -> int:
        return len(self.active_connections.get(session_id, []))

manager = ConnectionManager()
