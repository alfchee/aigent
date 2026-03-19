from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.llm import default_llm
from app.skills.registry import registry
from app.api.websockets import manager
from app.channels.telegram import telegram_bot
from app.core.scheduler import SchedulerService
from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox
from app.core.agent_graph import graph_app
from app.core.roles import role_manager
from app.core.chat_persistence import ChatPersistence
from app.api.telegram_webhook import router as telegram_webhook_router
from app.core.paths import repo_root, workspace_db_dir, workspace_config_dir
import logging
import json
import asyncio
import time
import uuid
from collections import defaultdict
from typing import Dict, List
import re
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("navibot")

scheduler = SchedulerService()
chat_persistence = ChatPersistence()
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


def extract_role_hint(message: str) -> str:
    stripped = message.strip()
    if stripped.startswith("@"):
        token = stripped.split(maxsplit=1)[0]
        role = token.removeprefix("@").strip().lower()
        return re.sub(r"[^a-z0-9_-]", "", role)
    return "default"


def resolve_openviking_workspace() -> str:
    conf_path = os.getenv("OPENVIKING_CONFIG_FILE")
    if conf_path:
        conf_file = Path(conf_path).expanduser()
    else:
        conf_file = workspace_config_dir() / "ov.conf"
    if not conf_file.exists():
        return "not_configured"
    try:
        data = json.loads(conf_file.read_text(encoding="utf-8"))
    except Exception:
        return f"invalid_config:{conf_file.as_posix()}"
    storage = data.get("storage", {})
    workspace = storage.get("workspace")
    if not workspace:
        return f"default_storage:{conf_file.as_posix()}"
    return Path(workspace).expanduser().as_posix()


def log_startup_paths() -> None:
    scheduler_db = (workspace_db_dir() / "scheduler.db").as_posix()
    episodic_db = (workspace_db_dir() / "episodic_memory.db").as_posix()
    chat_db = (workspace_db_dir() / "chat_messages.db").as_posix()
    roles_file = (workspace_config_dir() / "roles.json").as_posix()
    ov_config_file = os.getenv("OPENVIKING_CONFIG_FILE") or (workspace_config_dir() / "ov.conf").as_posix()
    logger.info("Startup paths -> repo_root=%s", repo_root().as_posix())
    logger.info("Startup paths -> scheduler_db=%s", scheduler_db)
    logger.info("Startup paths -> episodic_db=%s", episodic_db)
    logger.info("Startup paths -> chat_db=%s", chat_db)
    logger.info("Startup paths -> roles_config=%s", roles_file)
    logger.info("Startup paths -> openviking_config=%s", ov_config_file)
    logger.info("Startup paths -> openviking_workspace=%s", resolve_openviking_workspace())


def resolve_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    items = [item.strip() for item in raw.split(",")]
    return [item for item in items if item]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("NaviBot 2.0 (Phoenix) is starting up...")
    log_startup_paths()
    
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(telegram_webhook_router)

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
            user_message_id = payload.get("messageId") or str(uuid.uuid4())
            user_created_at = payload.get("createdAt")
            if not isinstance(user_created_at, int):
                user_created_at = int(time.time() * 1000)
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
            chat_persistence.save_message(
                message_id=user_message_id,
                session_id=session_id,
                conversation_id=conversation_id,
                role="user",
                text=text,
                created_at=user_created_at,
                meta={"source": "websocket"},
            )
            memory = session_memory.setdefault(session_id, MemoryController(user_id=session_id))
            memory.add_fact(text, path="facts/messages.md")

            code_to_run = extract_python_code(text)
            role_hint = extract_role_hint(text)
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
                    role_id=role_hint,
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
                    assistant_text = await graph_app.run_turn(
                        user_text=prompt_text,
                        user_id=session_id,
                        session_id=session_id,
                    )
                except Exception as e:
                    logger.exception("Error in AgentGraph runtime for session %s: %s", session_id, e)
                    try:
                        response = await default_llm.generate(
                            messages=[*history[:-1], {"role": "user", "content": prompt_text}]
                        )
                        assistant_text = response.choices[0].message.content or ""
                    except Exception as fallback_exc:
                        logger.exception(
                            "Fallback LLM error for session %s: %s",
                            session_id,
                            fallback_exc,
                        )
                        assistant_text = "Hubo un problema al generar la respuesta del agente."

            history.append({"role": "assistant", "content": assistant_text})
            if len(history) % 6 == 0:
                chunk = history[-6:]
                summary = "\n".join(f"{item['role']}: {item['content']}" for item in chunk)
                memory.save_session_summary(session_id, summary)

            assistant_message_id = str(uuid.uuid4())
            assistant_created_at = int(time.time() * 1000)
            chat_persistence.save_message(
                message_id=assistant_message_id,
                session_id=session_id,
                conversation_id=conversation_id,
                role="assistant",
                text=assistant_text,
                created_at=assistant_created_at,
                meta={"source": "websocket"},
            )

            await manager.send_json(
                {
                    "type": "assistant_message",
                    "conversationId": conversation_id,
                    "messageId": assistant_message_id,
                    "text": assistant_text,
                    "createdAt": assistant_created_at,
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


@app.get("/sandbox/metrics")
async def sandbox_metrics():
    return {"status": "ok", "metrics": default_sandbox.metrics_snapshot()}


@app.get("/memory/{session_id}/summaries")
async def memory_summaries(
    session_id: str,
    since_ts: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
):
    memory = session_memory.setdefault(session_id, MemoryController(user_id=session_id))
    if since_ts is not None:
        summaries = memory.get_summaries_since(session_id=session_id, since_ts=since_ts, limit=limit)
    else:
        summaries = memory.get_summaries_since(session_id=session_id, since_ts=0, limit=limit)
    return {"status": "ok", "session_id": session_id, "count": len(summaries), "items": summaries}


@app.get("/chat/{session_id}/messages")
async def chat_messages(
    session_id: str,
    conversation_id: str | None = Query(default=None, alias="conversationId"),
    before_created_at: int | None = Query(default=None, ge=0, alias="beforeCreatedAt"),
    limit: int = Query(default=50, ge=1, le=200),
):
    items = chat_persistence.list_messages(
        session_id=session_id,
        conversation_id=conversation_id,
        before_created_at=before_created_at,
        limit=limit,
    )
    return {"status": "ok", "session_id": session_id, "count": len(items), "items": items}


@app.get("/roles")
async def get_roles():
    snapshot = role_manager.snapshot()
    return {
        "status": "ok",
        "config_path": snapshot.config_path,
        "updated_at": snapshot.updated_at,
        "supervisor": snapshot.supervisor.model_dump(),
        "workers": [worker.model_dump() for worker in snapshot.workers],
    }


@app.post("/roles/reload")
async def reload_roles():
    snapshot = role_manager.reload()
    return {
        "status": "ok",
        "config_path": snapshot.config_path,
        "updated_at": snapshot.updated_at,
        "workers_count": len(snapshot.workers),
    }
