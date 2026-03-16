from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.core.llm import default_llm
from app.skills.registry import registry
from app.api.websockets import manager
from app.channels.telegram import telegram_bot
from app.core.scheduler import SchedulerService
from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox
import logging
import json
import asyncio
import time
import uuid
from collections import defaultdict
from typing import Dict, List
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("navibot")

scheduler = SchedulerService()
session_histories: Dict[str, List[Dict[str, str]]] = defaultdict(list)
session_memory: Dict[str, MemoryController] = {}


def extract_python_code(message: str) -> str:
    stripped = message.strip()
    if stripped.startswith("/python"):
        return stripped.replace("/python", "", 1).strip()
    fenced = re.findall(r"```python(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[0].strip()
    return ""

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
            await manager.send_json(
                {"type": "status", "state": "thinking", "action": "Analyzing", "details": "Processing user request"},
                session_id,
            )

            history = session_histories[session_id]
            history.append({"role": "user", "content": text})
            memory = session_memory.setdefault(session_id, MemoryController(user_id=session_id))
            memory.add_fact(text, path="facts/messages.md")

            code_to_run = extract_python_code(text)
            if code_to_run:
                await manager.send_json(
                    {
                        "type": "tool_call",
                        "tool_name": "python_sandbox",
                        "details": "Executing validated code",
                    },
                    session_id,
                )
                execution = await default_sandbox.execute_code(
                    code=code_to_run,
                    timeout=15,
                    session_id=session_id,
                )
                assistant_text = (
                    f"Resultado de ejecución:\n\nSTDOUT:\n{execution.stdout or '(vacío)'}\n\n"
                    f"STDERR:\n{execution.stderr or '(vacío)'}"
                )
                if execution.error:
                    assistant_text += f"\n\nERROR: {execution.error}"
            else:
                semantic_context = memory.retrieve_context(text)
                prompt_text = text
                if semantic_context:
                    prompt_text = f"{semantic_context}\n\nUser input:\n{text}"

                try:
                    response = await default_llm.generate(messages=[*history[:-1], {"role": "user", "content": prompt_text}])
                    assistant_text = response.choices[0].message.content or ""
                except Exception as e:
                    logger.exception(f"Error generating assistant response for session {session_id}: {e}")
                    assistant_text = "Hubo un problema al generar la respuesta del agente."

            history.append({"role": "assistant", "content": assistant_text})
            if len(history) % 6 == 0:
                chunk = history[-6:]
                summary = "\n".join(f"{item['role']}: {item['content']}" for item in chunk)
                memory.save_session_summary(session_id, summary)

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
