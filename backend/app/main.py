from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.core.agent import NaviBot
from app.api.files import router as files_router
from app.api.artifacts import router as artifacts_router
from app.api.workspace import router as workspace_router
from app.core.persistence import init_db, save_chat_message
from app.skills.scheduler import start_scheduler
import asyncio

app = FastAPI(title="NaviBot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, ge=1),
):
    from app.core.persistence import load_chat_messages_page

    try:
        return load_chat_messages_page(session_id=session_id, limit=limit, before_id=before_id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error while loading session history: {str(e)}",
        )


app.include_router(files_router)
app.include_router(artifacts_router)
app.include_router(workspace_router)

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    from app.core.runtime_context import reset_event_callback, reset_session_id, set_event_callback, set_session_id
    session_token = set_session_id(request.session_id)
    callback_token = set_event_callback(None)
    try:
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

            return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
