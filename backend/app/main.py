from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.core.llm import default_llm
from app.skills.registry import registry
from app.api.websockets import manager
from app.channels.telegram import telegram_bot
from app.core.scheduler import SchedulerService
import logging
import json
import asyncio
import time
import uuid
from collections import defaultdict
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("navibot")

scheduler = SchedulerService()
session_histories: Dict[str, List[Dict[str, str]]] = defaultdict(list)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("NaviBot 2.0 (Phoenix) is starting up...")
    
    # Start Scheduler
    scheduler.start()
    
    # Initialize Telegram (Webhook or Polling if configured)
    if telegram_bot.token:
        asyncio.create_task(telegram_bot.initialize())

    yield
    
    # Shutdown logic
    logger.info("NaviBot 2.0 (Phoenix) is shutting down...")
    scheduler.shutdown()
    if telegram_bot.token:
        await telegram_bot.shutdown()

app = FastAPI(
    title="NaviBot 2.0 (Phoenix)",
    description="Agentic Ecosystem Orchestrated by LangGraph",
    version="2.0.0",
    lifespan=lifespan
)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data} from session {session_id}")
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_json(
                    {
                        "type": "error",
                        "content": "Invalid JSON payload",
                        "ts": int(time.time() * 1000),
                    },
                    session_id,
                )
                continue

            msg_type = payload.get("type")

            if msg_type == "ping":
                await manager.send_json(
                    {"type": "pong", "ts": payload.get("ts", int(time.time() * 1000))},
                    session_id,
                )
                continue

            if msg_type != "user_message":
                await manager.send_json(
                    {"type": "ack", "content": "Message received", "ts": int(time.time() * 1000)},
                    session_id,
                )
                continue

            text = (payload.get("text") or "").strip()
            conversation_id = payload.get("conversationId") or session_id
            if not text:
                await manager.send_json(
                    {
                        "type": "error",
                        "content": "Empty message",
                        "conversationId": conversation_id,
                        "ts": int(time.time() * 1000),
                    },
                    session_id,
                )
                continue

            await manager.send_json({"type": "ack", "content": "Message received"}, session_id)

            history = session_histories[session_id]
            history.append({"role": "user", "content": text})

            try:
                response = await default_llm.generate(messages=history)
                assistant_text = response.choices[0].message.content or ""
            except Exception as e:
                logger.exception(f"Error generating assistant response for session {session_id}: {e}")
                assistant_text = "Hubo un problema al generar la respuesta del agente."

            history.append({"role": "assistant", "content": assistant_text})

            await manager.send_json(
                {
                    "type": "assistant_message",
                    "conversationId": conversation_id,
                    "messageId": str(uuid.uuid4()),
                    "text": assistant_text,
                    "createdAt": int(time.time() * 1000),
                },
                session_id,
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

@app.get("/")
async def root():
    return {"message": "Welcome to NaviBot 2.0 (The Phoenix)", "status": "operational"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
