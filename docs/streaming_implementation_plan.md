# Implementation Plan: Streaming Responses with Server-Sent Events (SSE)

## Problem Statement

The current `/api/chat` endpoint uses a request-response pattern that blocks until the entire agent execution completes. For complex tasks using the ReAct loop, this can take significant time (up to 300 seconds), creating a poor user experience where the frontend appears frozen with no feedback.

**Goal**: Implement Server-Sent Events (SSE) to stream real-time progress updates during agent execution, showing the user what the agent is "thinking" and doing at each step.

---

## User Review Required

> [!IMPORTANT]
> **Backward Compatibility**: The existing `/api/chat` endpoint will remain unchanged. A new `/api/chat/stream` endpoint will be added for SSE streaming. This ensures existing integrations continue to work.

> [!IMPORTANT]
> **Event Structure**: Events will be sent as JSON objects with a `type` field. The frontend must parse these events and handle different types appropriately. See the Event Types section below for details.

---

## Proposed Changes

### Dependencies

#### [MODIFY] [requirements.txt](file:///home/alfchee/Workspace/own/navibot/backend/requirements.txt)

Add the `sse-starlette` library for SSE support in FastAPI:

```diff
 fastapi
 uvicorn[standard]
 google-genai
 playwright
 apscheduler
 pydantic
 python-dotenv
 httpx
 sqlalchemy
+sse-starlette
```

---

### Core Backend Components

#### [MODIFY] [react_engine.py](file:///home/alfchee/Workspace/own/navibot/backend/app/core/react_engine.py)

**Changes**:
- Add optional `event_callback` parameter to `ReActLoop.__init__()` and `execute()` methods
- Emit events at key points in the execution loop:
  - **Iteration start**: When a new reasoning cycle begins
  - **Tool call**: When the agent decides to use a tool (if we can detect it)
  - **Response received**: When the agent provides a response
  - **Completion**: When the loop terminates
- Events will be dictionaries with `type`, `data`, and `timestamp` fields

**Key modifications**:
```python
class ReActLoop:
    def __init__(
        self, 
        agent,
        max_iterations: int = 10,
        timeout_seconds: int = 300,
        event_callback: Optional[Callable] = None  # NEW
    ):
        self.event_callback = event_callback
        # ... existing code
    
    async def execute(self, initial_prompt: str) -> Dict[str, Any]:
        # Emit events throughout execution
        await self._emit_event("iteration_start", {...})
        await self._emit_event("thinking", {...})
        await self._emit_event("response", {...})
        await self._emit_event("completion", {...})
```

#### [MODIFY] [agent.py](file:///home/alfchee/Workspace/own/navibot/backend/app/core/agent.py)

**Changes**:
- Update `send_message_with_react()` to accept and pass through the `event_callback` parameter to `ReActLoop`

**Key modifications**:
```python
async def send_message_with_react(
    self, 
    message: str,
    max_iterations: int = 10,
    timeout_seconds: int = 300,
    event_callback: Optional[Callable] = None  # NEW
) -> Dict[str, Any]:
    react_loop = ReActLoop(
        agent=self,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        event_callback=event_callback  # NEW
    )
    return await react_loop.execute(message)
```

#### [MODIFY] [main.py](file:///home/alfchee/Workspace/own/navibot/backend/app/main.py)

**Changes**:
- Add new `/api/chat/stream` endpoint using `EventSourceResponse` from `sse-starlette`
- Create an async generator that yields SSE events
- Keep existing `/api/chat` endpoint unchanged for backward compatibility

**New endpoint structure**:
```python
from sse_starlette.sse import EventSourceResponse

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        # Create event queue
        event_queue = asyncio.Queue()
        
        # Define callback to push events to queue
        async def event_callback(event_type: str, data: dict):
            await event_queue.put({"type": event_type, "data": data})
        
        # Start agent execution in background
        task = asyncio.create_task(
            bot.send_message_with_react(
                request.message,
                max_iterations=request.max_iterations,
                event_callback=event_callback
            )
        )
        
        # Yield events as they arrive
        while not task.done():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue
        
        # Send final result
        result = await task
        yield {"type": "final", "data": result}
    
    return EventSourceResponse(event_generator())
```

---

## Event Types

The streaming endpoint will emit the following event types:

| Event Type | Description | Data Fields |
|:-----------|:------------|:------------|
| `iteration_start` | New reasoning cycle begins | `iteration`: number, `timestamp`: ISO string |
| `thinking` | Agent is processing/reasoning | `message`: string (e.g., "Analyzing request...") |
| `tool_call` | Agent is calling a tool | `tool_name`: string, `arguments`: dict |
| `observation` | Tool execution result | `result`: string/dict |
| `response` | Agent provides text response | `text`: string |
| `completion` | Execution finished | `reason`: string, `iterations`: number, `time`: float |
| `error` | Error occurred | `message`: string, `details`: string |

**Example event**:
```json
{
  "type": "thinking",
  "data": {
    "message": "Starting iteration 1 of 10",
    "timestamp": "2026-02-06T05:49:54Z"
  }
}
```

---

## Verification Plan

### Automated Tests

1. **Test SSE endpoint with httpie**:
```bash
http --stream POST http://localhost:8231/api/chat/stream \
  message="List the files in the current directory" \
  use_react_loop:=true
```

2. **Test event structure**:
   - Verify all events have `type` and `data` fields
   - Confirm JSON is valid
   - Check timestamp formats

3. **Test error handling**:
   - Send invalid requests
   - Test timeout scenarios
   - Verify error events are emitted

### Manual Verification

1. **Frontend Integration**:
   - User will need to update Vue.js frontend to consume SSE events
   - Display progress indicators based on event types
   - Show "thinking" states, tool calls, and observations in real-time

2. **Performance Testing**:
   - Test with long-running tasks (multiple iterations)
   - Verify events arrive in real-time without buffering
   - Check memory usage during streaming

---

## Frontend Integration Notes

The Vue.js frontend will need to:

1. **Use EventSource API** to connect to `/api/chat/stream`
2. **Parse JSON events** from the SSE stream
3. **Update UI** based on event types:
   - Show spinner/progress for `thinking` events
   - Display tool calls and observations
   - Show final response on `completion`

**Example frontend code**:
```javascript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: 'Hello', use_react_loop: true })
});

eventSource.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  
  switch(type) {
    case 'thinking':
      showThinkingIndicator(data.message);
      break;
    case 'tool_call':
      showToolCall(data.tool_name, data.arguments);
      break;
    case 'response':
      appendResponse(data.text);
      break;
    case 'completion':
      hideThinkingIndicator();
      break;
  }
};
```

> [!NOTE]
> The standard EventSource API doesn't support POST requests with custom bodies. The frontend may need to use a library like `eventsource` (npm) or implement a custom SSE client using `fetch()` with `ReadableStream`.
