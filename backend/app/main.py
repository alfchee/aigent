from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.agent import NaviBot
from app.api.files import router as files_router
from app.api.artifacts import router as artifacts_router
from app.api.workspace import router as workspace_router
from app.api.sessions import router as sessions_router
from app.core.persistence import init_db, save_chat_message
from app.skills.scheduler import start_scheduler
import asyncio
import logging
import time
import uuid

from app.core.logging import setup_logging, notify_alert
from app.core.runtime_context import reset_request_id, set_request_id

setup_logging()

app = FastAPI(title="NaviBot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("navibot.api")

# Initialize Agent
bot = NaviBot()

# Start Scheduler on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    start_scheduler()

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    use_react_loop: bool = False  # Default to simple mode for API backward compatibility
    max_iterations: int = 10
    include_trace: bool = False  # Return reasoning trace in response

class ChatResponse(BaseModel):
    response: str
    iterations: int | None = None
    tool_calls: list[dict] | None = None
    reasoning_trace: list[str] | None = None
    termination_reason: str | None = None
    execution_time_seconds: float | None = None

@app.get("/")
async def root():
    return {"message": "NaviBot Backend is running", "status": "ok"}

app.include_router(files_router)
app.include_router(artifacts_router)
app.include_router(workspace_router)
app.include_router(sessions_router)

def _truncate_text(value: str, limit: int = 500) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _parse_json_body(body: bytes) -> dict | None:
    try:
        import json

        data = json.loads(body.decode("utf-8"))
        if isinstance(data, dict) and "message" in data and isinstance(data["message"], str):
            data["message"] = _truncate_text(data["message"])
        return data
    except Exception:
        return None


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = set_request_id(request_id)
    start = time.perf_counter()
    body = await request.body()
    body_json = _parse_json_body(body) if body else None
    logger.info(
        "request_start",
        extra={
            "event": "request_start",
            "payload": {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "client": request.client.host if request.client else None,
                "body": body_json,
            },
        },
    )
    try:
        response = await call_next(request)
    except Exception:
        raise
    finally:
        if "response" in locals():
            request.state.status_code = response.status_code
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_end",
            extra={
                "event": "request_end",
                "payload": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": getattr(request.state, "status_code", None),
                    "duration_ms": round(duration_ms, 2),
                },
            },
        )
        reset_request_id(token)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_id = uuid.uuid4().hex
    logger.exception(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "payload": {
                "error_id": error_id,
                "path": request.url.path,
                "method": request.method,
            },
        },
    )
    await notify_alert(
        {
            "type": "chat_failure" if request.url.path.startswith("/api/chat") else "request_failure",
            "error_id": error_id,
            "path": request.url.path,
            "method": request.method,
        }
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error_id": error_id})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    from app.core.runtime_context import reset_event_callback, reset_session_id, set_event_callback, set_session_id
    session_token = set_session_id(request.session_id)
    callback_token = set_event_callback(None)
    try:
        logger.info(
            "chat_request_start",
            extra={
                "event": "chat_request_start",
                "payload": {
                    "session_id": request.session_id,
                    "use_react_loop": request.use_react_loop,
                    "max_iterations": request.max_iterations,
                    "include_trace": request.include_trace,
                    "message": _truncate_text(request.message),
                },
            },
        )
        # Ensure session is loaded to get baseline history length
        await bot.ensure_session(request.session_id)
        pre_history = bot.get_history(request.session_id)
        pre_len = len(pre_history) if pre_history else 0

        # Save user message immediately (as structured content)
        user_content = {"role": "user", "parts": [{"text": request.message}]}
        save_chat_message(request.session_id, "user", user_content)

        if request.use_react_loop:
            result = await bot.send_message_with_react(
                request.message,
                max_iterations=request.max_iterations
            )

            response_text = result["response"]
            # save_chat_message call removed, handled by history sync below
            
            # Sync history
            post_history = bot.get_history(request.session_id)
            new_items = post_history[pre_len:]
            # Skip the first item if it matches the user message we already saved
            if new_items and new_items[0].role == "user":
                new_items = new_items[1:]
            
            for item in new_items:
                save_chat_message(request.session_id, item.role, item)

            logger.info(
                "chat_request_end",
                extra={
                    "event": "chat_request_end",
                    "payload": {
                        "session_id": request.session_id,
                        "mode": "react",
                        "response_length": len(response_text) if response_text else 0,
                        "iterations": result.get("iterations"),
                        "termination_reason": result.get("termination_reason"),
                    },
                },
            )
            return ChatResponse(
                response=response_text,
                iterations=result["iterations"] if request.include_trace else None,
                tool_calls=result.get("tool_calls") if request.include_trace else None,
                reasoning_trace=result.get("reasoning_trace") if request.include_trace else None,
                termination_reason=result.get("termination_reason") if request.include_trace else None,
                execution_time_seconds=result.get("execution_time_seconds") if request.include_trace else None
            )
        else:
            response_text = await bot.send_message(request.message)
            # save_chat_message call removed, handled by history sync below
            
            # Sync history
            post_history = bot.get_history(request.session_id)
            new_items = post_history[pre_len:]
            if new_items and new_items[0].role == "user":
                new_items = new_items[1:]
            
            for item in new_items:
                save_chat_message(request.session_id, item.role, item)

            logger.info(
                "chat_request_end",
                extra={
                    "event": "chat_request_end",
                    "payload": {
                        "session_id": request.session_id,
                        "mode": "simple",
                        "response_length": len(response_text) if response_text else 0,
                    },
                },
            )
            return ChatResponse(response=response_text)
    except Exception as e:
        error_id = uuid.uuid4().hex
        logger.exception(
            "chat_request_error",
            extra={
                "event": "chat_request_error",
                "payload": {
                    "error_id": error_id,
                    "session_id": request.session_id,
                    "use_react_loop": request.use_react_loop,
                },
            },
        )
        await notify_alert(
            {
                "type": "chat_failure",
                "error_id": error_id,
                "session_id": request.session_id,
                "use_react_loop": request.use_react_loop,
            }
        )
        raise HTTPException(status_code=500, detail=f"Internal Server Error ({error_id})")
    finally:
        reset_session_id(session_token)
        reset_event_callback(callback_token)

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming endpoint using Server-Sent Events (SSE).
    Provides real-time updates during agent execution.
    """
    from sse_starlette.sse import EventSourceResponse
    import json
    
    async def event_generator():
        # Create event queue for communication between agent and SSE stream
        event_queue = asyncio.Queue()
        task_complete = asyncio.Event()
        final_result = None
        task_error = None
        
        # Define callback to push events to queue
        async def event_callback(event_type: str, data: dict):
            await event_queue.put({
                "event": event_type,
                "data": data
            })
        
        # Start agent execution in background task
        async def run_agent():
            nonlocal final_result, task_error
            from app.core.runtime_context import reset_event_callback, reset_session_id, set_event_callback, set_session_id
            session_token = set_session_id(request.session_id)
            callback_token = set_event_callback(event_callback)
            
            # Ensure session loaded and get baseline
            await bot.ensure_session(request.session_id)
            pre_history = bot.get_history(request.session_id)
            pre_len = len(pre_history) if pre_history else 0
            
            try:
                if request.use_react_loop:
                    final_result = await bot.send_message_with_react(
                        request.message,
                        max_iterations=request.max_iterations,
                        event_callback=event_callback
                    )
                else:
                    # For simple mode, just send the message
                    response_text = await bot.send_message(request.message)
                    final_result = {"response": response_text}
                
                # Sync history
                post_history = bot.get_history(request.session_id)
                new_items = post_history[pre_len:]
                if new_items and new_items[0].role == "user":
                    new_items = new_items[1:]
                
                for item in new_items:
                    save_chat_message(request.session_id, item.role, item)
                    
            except Exception as e:
                logger.exception(
                    "chat_stream_error",
                    extra={
                        "event": "chat_stream_error",
                        "payload": {
                            "session_id": request.session_id,
                            "use_react_loop": request.use_react_loop,
                        },
                    },
                )
                await notify_alert(
                    {
                        "type": "chat_stream_failure",
                        "session_id": request.session_id,
                        "use_react_loop": request.use_react_loop,
                    }
                )
                task_error = e
            finally:
                reset_session_id(session_token)
                reset_event_callback(callback_token)
                task_complete.set()
        
        user_content = {"role": "user", "parts": [{"text": request.message}]}
        save_chat_message(request.session_id, "user", user_content)
        
        # Start the agent task
        agent_task = asyncio.create_task(run_agent())
        
        try:
            # Stream events as they arrive
            while not task_complete.is_set():
                try:
                    # Wait for event with timeout to check task completion
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    # Yield SSE formatted event
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"])
                    }
                except asyncio.TimeoutError:
                    # No event available, continue waiting
                    continue
            
            # Drain any remaining events in the queue
            while not event_queue.empty():
                event = event_queue.get_nowait()
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }
            
            # Send final result or error
            if task_error:
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": "Task execution failed",
                        "details": str(task_error)
                    })
                }
            elif final_result:
                # History saving is handled in run_agent now
                yield {
                    "event": "final",
                    "data": json.dumps(final_result)
                }
                
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({
                    "message": "Streaming error",
                    "details": str(e)
                })
            }
    
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8231, reload=True)
