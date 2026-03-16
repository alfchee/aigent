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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("navibot")

scheduler = SchedulerService()

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
            # Handle incoming message
            # For now, just echo or pass to agent (future)
            logger.info(f"Received message: {data} from session {session_id}")
            
            # TODO: Integrate with AgentGraph here
            # graph.invoke(...)
            
            await manager.send_json({"type": "ack", "content": "Message received"}, session_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

@app.get("/")
async def root():
    return {"message": "Welcome to NaviBot 2.0 (The Phoenix)", "status": "operational"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
