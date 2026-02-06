from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.agent import NaviBot
from app.skills.scheduler import start_scheduler
import asyncio

app = FastAPI(title="NaviBot API", version="0.1.0")

# Initialize Agent
bot = NaviBot()

# Start Scheduler on startup
@app.on_event("startup")
async def startup_event():
    start_scheduler()

class ChatRequest(BaseModel):
    message: str
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

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        if request.use_react_loop:
            # Use ReAct loop for autonomous multi-turn execution
            result = await bot.send_message_with_react(
                request.message,
                max_iterations=request.max_iterations
            )
            
            return ChatResponse(
                response=result["response"],
                iterations=result["iterations"] if request.include_trace else None,
                tool_calls=result.get("tool_calls") if request.include_trace else None,
                reasoning_trace=result.get("reasoning_trace") if request.include_trace else None,
                termination_reason=result.get("termination_reason") if request.include_trace else None,
                execution_time_seconds=result.get("execution_time_seconds") if request.include_trace else None
            )
        else:
            # Simple single-turn execution (backward compatibility)
            response_text = await bot.send_message(request.message)
            return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            except Exception as e:
                task_error = e
            finally:
                task_complete.set()
        
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
