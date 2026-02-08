# NaviBot Backend Overview

This document provides a comprehensive overview of the NaviBot backend architecture, its features, and available API endpoints.

## System Architecture

The NaviBot backend is built using **FastAPI**, a modern, high-performance web framework for building APIs with Python. It integrates several key components:

- **FastAPI**: Manages REST endpoints and provides the web server interface.
- **Google GenAI SDK**: Powers the core agent logic using the `gemini-2.0-flash` model.
- **APScheduler**: Handles persistent task scheduling for both one-off and recurring agent executions.
- **Playwright**: Enables the agent to perform web browsing and automation tasks.

## Core Components

### 1. NaviBot Agent (`app/core/agent.py`)
The `NaviBot` class is the central intelligence of the system.
- **AI Model**: Defaults to `gemini-2.0-flash`.
- **Tool Registration**: Automatically registers skills from the `app/skills` directory.
- **Chat Sessions**: Manages asynchronous chat sessions with automatic function calling enabled.
- **History Management**: Abstraction layer (`get_history`) to handle different Gemini SDK history access patterns (sync vs async, property vs method).
- **Execution Modes**:
  - **Simple Mode**: Single-turn execution via `send_message()` for quick responses.
  - **ReAct Mode**: Multi-turn autonomous execution via `send_message_with_react()` for complex tasks.

### 2. ReAct Loop Engine (`app/core/react_engine.py`)
Implements the **ReAct (Reason + Act)** cognitive loop for autonomous multi-turn execution.
- **Iterative Reasoning**: Agent can execute multiple reasoning cycles before responding.
- **Observation & Reflection**: Processes tool results and determines next actions.
- **Termination Conditions**: Natural completion, max iterations, timeout, or error.
- **Reasoning Trace**: Comprehensive logging of all execution steps.
- **Configurable Limits**: Max iterations (default: 10) and timeout (default: 300s).

### 3. Scheduler Service (`app/core/scheduler_service.py`)
Provides persistent job scheduling using **APScheduler** and **SQLAlchemy**.

#### Persistence
- **Database**: Uses `scheduler.db` (SQLite) to store job metadata.
- **Reliability**: Jobs survive server restarts. If the server is down when a job was supposed to run, it will typically execute upon startup (depending on misfire parameters).

#### Job Types
- **Date-based**: One-off execution at a specific ISO timestamp (`YYYY-MM-DD HH:MM:SS`).
- **Interval-based**: Recurring execution every $N$ seconds.

#### Execution Lifecycle
1. The scheduler monitors the database for due jobs.
2. When a job triggers, it calls `execute_agent_task(prompt, use_react_loop, max_iterations)`.
3. This function:
    - Prints an execution log with mode indicator (ReAct vs Simple).
    - Instantiates a **fresh** `NaviBot` instance.
    - Sends the `prompt` to the agent using the selected execution mode.
    - Logs the final response, iteration count, and reasoning trace (if ReAct mode).
    - **ReAct Mode** (default): Enables autonomous multi-turn execution for complex tasks.
    - **Simple Mode**: Single-turn execution for straightforward queries.

---

| Skill | Tools Provided | Description |
| :--- | :--- | :--- |
| **System** | `list_files`, `read_file`, `create_file`, `update_file` | Basic filesystem operations. |
| **Browser** | `navigate`, `get_page_content`, `screenshot`, `close_browser` | Web automation and content extraction. |
| **Scheduler** | `schedule_task`, `schedule_interval_task` | Ability for the agent to schedule its own future tasks. |
| **Workspace** | `create_doc`, `send_email`, `create_calendar_event` | Placeholders for Google Workspace integrations. |

## Tool and Skill Reference (Agent Tooling)

This section is the authoritative tool reference for the agent. Every tool call must include all required parameters with the correct types. Do not call tools with empty arguments.

### System Skill (Filesystem)

#### list_files
**Signature**: `list_files(directory: str = "/") -> str`  
**Parameters**:
- `directory` (optional, string): Virtual directory inside the session workspace. Use `/` for root.
**Returns**:
- JSON string: `{"directory": "...", "files": [{"path": "...", "size_bytes": int, "modified_at": "ISO-8601", "mime_type": "..."}, ...]}`
- Error string: `"Error listing files: ..."`

**Examples**:
```
list_files()
```
```
list_files(directory="/reports")
```

#### read_file
**Signature**: `read_file(filepath: str, max_bytes: int = 1_000_000) -> str`  
**Parameters**:
- `filepath` (required, string): Virtual path to the file inside the session workspace.
- `max_bytes` (optional, integer): Max bytes to read before truncation behavior.
**Returns**:
- Text content for text-like files.
- JSON string for binary or oversized files:
  - `{"path": "...", "mime_type": "...", "size_bytes": int, "truncated": true}`
  - `{"path": "...", "mime_type": "...", "size_bytes": int, "base64": "..."}`
- Error string: `"Error reading file: ..."`

**Examples**:
```
read_file(filepath="notes/todo.txt")
```
```
read_file(filepath="assets/logo.png", max_bytes=200000)
```

#### create_file
**Signature**: `create_file(filepath: str, content: str, encoding: str = "utf-8") -> str`  
**Parameters**:
- `filepath` (required, string): Virtual path + filename where the file will be written.
- `content` (required, string): File contents.
- `encoding` (optional, string): `"utf-8"` for text or `"base64"` for binary content.
**Returns**:
- JSON string: `{"saved": {"path": "...", "size_bytes": int, "modified_at": "ISO-8601", "mime_type": "..."}}`
- Error string: `"Error creating file: ..."`

**Examples (correct usage with required parameters)**:
```
create_file(filepath="notes/todo.txt", content="Buy milk\nCall Sam\n")
```
```
create_file(filepath="reports/summary.md", content="# Summary\n- Q1 results\n")
```
```
create_file(filepath="images/logo.png", content="iVBORw0KGgoAAA...", encoding="base64")
```
```
create_file(filepath="index.html", content="<!doctype html><h1>Hola</h1>")
```

#### update_file
**Signature**: `update_file(filepath: str, start_line: int, end_line: int, new_content: str) -> str`  
**Parameters**:
- `filepath` (required, string): Virtual path to the target file.
- `start_line` (required, integer): 1-based line to start replacement.
- `end_line` (required, integer): 1-based line to end replacement. Use `0` or a value less than `start_line` to replace only `start_line`.
- `new_content` (required, string): Replacement text (include trailing newline if needed).
**Returns**:
- JSON string: `{"saved": {"path": "...", "size_bytes": int, "modified_at": "ISO-8601", "mime_type": "..."}}`
- Error string: `"Error updating file: ..."`

**Examples**:
```
update_file(filepath="notes/todo.txt", start_line=2, end_line=2, new_content="Call Alex\n")
```
```
update_file(filepath="notes/todo.txt", start_line=1, end_line=0, new_content="Buy coffee\n")
```

### Browser Skill

#### navigate
**Signature**: `navigate(url: str) -> str`  
**Parameters**:
- `url` (required, string): Full URL to open.
**Returns**:
- Success string with page title, or error string.

**Example**:
```
navigate(url="https://example.com")
```

#### get_page_content
**Signature**: `get_page_content() -> str`  
**Parameters**: none  
**Returns**:
- HTML content (truncated to 10,000 chars) or error string.

**Example**:
```
get_page_content()
```

#### screenshot
**Signature**: `screenshot(filename: str = "screenshot.png") -> str`  
**Parameters**:
- `filename` (optional, string): Virtual path to save the screenshot in the session workspace.
**Returns**:
- JSON string: `{"saved": {"path": "...", "size_bytes": int, "modified_at": "ISO-8601", "mime_type": "..."}}`
- Error string.

**Example**:
```
screenshot(filename="shots/homepage.png")
```

#### close_browser
**Signature**: `close_browser() -> str`  
**Parameters**: none  
**Returns**:
- `"Browser closed."` or error string.

**Example**:
```
close_browser()
```

### Scheduler Skill

#### schedule_task
**Signature**: `schedule_task(prompt: str, execute_at: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10) -> str`  
**Parameters**:
- `prompt` (required, string): Instruction for the agent.
- `execute_at` (required, string): ISO timestamp `YYYY-MM-DD HH:MM:SS`.
- `session_id` (optional, string): Session/workspace id.
- `use_react_loop` (optional, boolean): Use ReAct loop for execution.
- `max_iterations` (optional, integer): ReAct loop iteration cap.
**Returns**:
- Success string confirming scheduling, or error string.

**Example**:
```
schedule_task(prompt="Generate daily report", execute_at="2026-02-08 09:00:00", session_id="sales")
```

#### schedule_interval_task
**Signature**: `schedule_interval_task(prompt: str, interval_seconds: int, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10) -> str`  
**Parameters**:
- `prompt` (required, string): Instruction for the agent.
- `interval_seconds` (required, integer): Interval in seconds.
- `session_id` (optional, string): Session/workspace id.
- `use_react_loop` (optional, boolean): Use ReAct loop for execution.
- `max_iterations` (optional, integer): ReAct loop iteration cap.
**Returns**:
- Success string confirming scheduling, or error string.

**Example**:
```
schedule_interval_task(prompt="Check status dashboard", interval_seconds=3600, session_id="ops")
```

### Workspace Skill (Placeholders)

#### create_doc
**Signature**: `create_doc(title: str, content: str) -> str`  
**Parameters**:
- `title` (required, string): Document title.
- `content` (required, string): Document body.
**Returns**:
- Mock success string.

**Example**:
```
create_doc(title="Meeting Notes", content="Agenda:\n- Budget\n")
```

#### send_email
**Signature**: `send_email(to: str, subject: str, body: str) -> str`  
**Parameters**:
- `to` (required, string): Recipient email address.
- `subject` (required, string): Email subject.
- `body` (required, string): Email body text.
**Returns**:
- Mock success string.

**Example**:
```
send_email(to="alex@example.com", subject="Status", body="All tasks completed.")
```

#### create_calendar_event
**Signature**: `create_calendar_event(summary: str, start_time: str, end_time: str) -> str`  
**Parameters**:
- `summary` (required, string): Event title.
- `start_time` (required, string): Start time.
- `end_time` (required, string): End time.
**Returns**:
- Mock success string.

**Example**:
```
create_calendar_event(summary="Sprint Planning", start_time="2026-02-08 10:00:00", end_time="2026-02-08 11:00:00")
```

## API Endpoints

The backend runs on port **8231** by default.

### Health Check
- **GET `/`**: Returns the status and version of the API.

### Chat Interface
- **POST `/api/chat`**: Sends a message to the NaviBot agent (blocking).
    - **Request Body**: `{"message": "string", "use_react_loop": bool}`
    - **Response**: `{"response": "string", ...}`

- **POST `/api/chat/stream`**: Sends a message and receives real-time progress via Server-Sent Events (SSE).
    - **Request Body**: Same as `/api/chat`
    - **Stream Events**:
        - `start`: Initial task setup
        - `iteration_start`: New reasoning cycle
        - `thinking`: Progress message
        - `tool_call`: (Planned) Tool execution start
        - `observation`: (Planned) Tool results
        - `response`: Text provided by agent
        - `completion`: Loop finished
        - `final`: Final aggregated result (JSON)
        - `error`: Error details

## Configuration

Environment variables are managed via a `.env` file in the `backend/` directory:
- `GOOGLE_API_KEY`: Required for interacting with the Gemini model.

## Running the Backend

To start the backend server with the default configuration:
```bash
cd backend
python -m app.main
```
This starts the FastAPI server on `0.0.0.0:8231` with auto-reload enabled.
