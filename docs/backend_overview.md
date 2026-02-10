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
- **AI Model**: Defaults to `gemini-2.0-flash` (dynamically configurable).
- **Tool Registration**: Automatically registers skills from the `app/skills` directory (`scheduler`, `browser`, `workspace`, `search`, `reader`, `code_execution`).
- **Prompt Architecture (The "Sandwich")**: Implements a layered system instruction structure:
  1. **Personality Layer**: User-defined persona and tone (from settings).
  2. **Capabilities Layer**: Dynamic tool definitions and technical instructions (`tool_reference`).
  3. **Search Policy Layer**: Strict rules for information retrieval (`SEARCH_POLICY`).
  4. **Base Constraints Layer**: Non-negotiable security, formatting, and privacy rules (`BASE_CONSTRAINTS`).
- **Execution Modes**:
  - **Simple Mode**: Single-turn execution via `send_message()`.
  - **ReAct Mode**: Multi-turn autonomous execution via `send_message_with_react()` for complex tasks.

### 2. ReAct Loop Engine (`app/core/react_engine.py`)
Implements the **ReAct (Reason + Act)** cognitive loop for autonomous multi-turn execution.
- **Iterative Reasoning**: Agent can execute multiple reasoning cycles before responding.
- **Observation & Reflection**: Processes tool results and determines next actions.
- **Termination Conditions**: Natural completion, max iterations, timeout, or error.
- **Reasoning Trace**: Comprehensive logging of all execution steps.

### 3. Scheduler Service (`app/core/scheduler_service.py`)
Provides persistent job scheduling using **APScheduler** and **SQLAlchemy**.

#### Persistence
- **Database**: Uses `navibot.db` (SQLite) to store job metadata.
- **Reliability**: Jobs survive server restarts.

#### Job Types
- **Date-based**: One-off execution at a specific ISO timestamp (`YYYY-MM-DD HH:MM:SS`).
- **Interval-based**: Recurring execution every $N$ seconds.

---

## Session History Retrieval

The backend exposes a paginated endpoint to retrieve historical chat content for an existing session and render it in the UI.

### Sessions CRUD
- `GET /api/sessions`: list sessions (ordered by `updated_at desc`)
- `POST /api/sessions`: create session (id optional)
- `PATCH /api/sessions/{session_id}`: update title
- `DELETE /api/sessions/{session_id}`: delete session + chat/tool history + workspace files
- `POST /api/sessions/{session_id}/autotitle`: generate a short title (Gemini if available, fallback otherwise)

### GET `/api/sessions/{session_id}/messages`
- **Purpose**: Load previously stored chat messages for a session (supports lazy loading).
- **Query params**:
  - `limit` (int, default 50, max 200): page size
  - `before_id` (int, optional): load messages older than this message id
- **Response**:
  - `items` are returned in chronological order (oldest → newest within the page).
  - `has_more` and `next_before_id` support loading older pages.

---

## Tool and Skill Reference (Agent Tooling)

This section is the authoritative tool reference for the agent. Every tool call must include all required parameters with the correct types. Do not call tools with empty arguments.

### 1. System Skill (Filesystem)

#### list_files
**Signature**: `list_files(directory: str = "/") -> str`  
**Parameters**:
- `directory` (optional, string): Virtual directory inside the session workspace. Use `/` for root.
**Returns**:
- JSON string: `{"directory": "...", "files": [{"path": "...", "size_bytes": int, "modified_at": "ISO-8601", "mime_type": "..."}, ...]}`
- Error string: `"Error listing files: ..."`

**Examples**:
```python
list_files()
list_files(directory="/reports")
```

#### read_file
**Signature**: `read_file(filepath: str, max_bytes: int = 1_000_000) -> str`  
**Parameters**:
- `filepath` (required, string): Virtual path to the file inside the session workspace.
- `max_bytes` (optional, integer): Max bytes to read before truncation behavior.
**Returns**:
- Text content for text-like files (including PDFs via text extraction).
- JSON string for binary or oversized files:
  - `{"path": "...", "mime_type": "...", "size_bytes": int, "truncated": true}`
  - `{"path": "...", "mime_type": "...", "size_bytes": int, "base64": "..."}`
- Error string: `"Error reading file: ..."`

**Examples**:
```python
read_file(filepath="notes/todo.txt")
read_file(filepath="docs/specs.pdf")
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

**Examples**:
```python
create_file(filepath="notes/todo.txt", content="Buy milk\nCall Sam\n")
create_file(filepath="images/logo.png", content="iVBORw0KGgoAAA...", encoding="base64")
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
```python
update_file(filepath="notes/todo.txt", start_line=2, end_line=2, new_content="Call Alex\n")
```

### 2. Search Skill & Reader Skill

**Search Policy**:
1. **Google Grounding**: (Native) First priority for general queries.
2. **Brave Search**: Second priority if grounding fails or for specific API usage.
3. **DuckDuckGo**: Fallback only.

#### search_brave
**Signature**: `search_brave(query: str, count: int = 5, offset: int = 0, lang: str = "es") -> str`  
**Parameters**:
- `query` (required, string): Search terms.
- `count` (optional, int): Number of results (default 5).
- `offset` (optional, int): Pagination offset.
- `lang` (optional, string): Language code (default "es").
**Returns**:
- JSON string with search results (title, url, description).

**Example**:
```python
search_brave(query="latest python features", count=3)
```

#### search_duckduckgo_fallback
**Signature**: `search_duckduckgo_fallback(query: str, max_results: int = 5) -> str`  
**Parameters**:
- `query` (required, string): Search terms.
- `max_results` (optional, int): Number of results.
**Returns**:
- JSON string with search results.

#### read_web_content
**Signature**: `read_web_content(url: str, max_chars: int = 20000, timeout: float = 10.0) -> str`  
**Parameters**:
- `url` (required, string): URL to fetch.
- `max_chars` (optional, int): limit content length (default 20000).
- `timeout` (optional, float): request timeout.
**Returns**:
- JSON string containing markdown-converted content, metadata, or error message.

**Example**:
```python
read_web_content(url="https://example.com/article")
```

### 3. Browser Skill (Playwright)

#### navigate
**Signature**: `navigate(url: str) -> str`  
**Parameters**:
- `url` (required, string): Full URL to open.
**Returns**:
- Success string with page title, or error string.

#### get_page_content
**Signature**: `get_page_content() -> str`  
**Parameters**: none  
**Returns**:
- HTML content (truncated to 10,000 chars) or error string.

#### screenshot
**Signature**: `screenshot(filename: str = "screenshot.png") -> str`  
**Parameters**:
- `filename` (optional, string): Virtual path to save the screenshot.
**Returns**:
- JSON string: `{"saved": {...}}` or error string.

#### close_browser
**Signature**: `close_browser() -> str`  
**Parameters**: none  
**Returns**:
- `"Browser closed."` or error string.

### 4. Code Execution Skill (Python)

Use this skill for **numerical calculations**, **data analysis**, or **visualization generation**. Do not use for file editing (use filesystem) or web browsing.

#### execute_python
**Signature**: `execute_python(code: str, timeout_seconds: int = 30, auto_correct: bool = True, max_attempts: int = 3) -> str`  
**Parameters**:
- `code` (required, string): Python code to execute.
- `timeout_seconds` (optional, integer): Max execution time (default 30).
- `auto_correct` (optional, boolean): Enable best-effort auto-correction (default True).
- `max_attempts` (optional, integer): Max retries (default 3).
**Returns**:
- JSON string with `status`, `stdout`, `stderr`, `created_files`, etc.

**Examples**:
```python
execute_python(code="print(sum(range(100)))")
execute_python(code="import math\nprint(math.sin(1.23))")
```

### 5. Scheduler Skill

#### schedule_task
**Signature**: `schedule_task(prompt: str, execute_at: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10) -> str`  
**Parameters**:
- `prompt` (required, string): Instruction for the agent.
- `execute_at` (required, string): ISO timestamp `YYYY-MM-DD HH:MM:SS`.
- `session_id` (optional, string): Session/workspace id.
- `use_react_loop` (optional, boolean): Use ReAct loop.
- `max_iterations` (optional, integer): ReAct loop iteration cap.

#### schedule_interval_task
**Signature**: `schedule_interval_task(prompt: str, interval_seconds: int, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10) -> str`  
**Parameters**:
- `prompt` (required, string): Instruction for the agent.
- `interval_seconds` (required, integer): Interval in seconds.

### 6. Workspace Skill (Mocks)

- `create_doc(title: str, content: str) -> str`
- `send_email(to: str, subject: str, body: str) -> str`
- `create_calendar_event(summary: str, start_time: str, end_time: str) -> str`

---

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
    - **Stream Events**: `start`, `iteration_start`, `thinking`, `tool_call`, `observation`, `response`, `completion`, `final`, `error`.

### Settings & Models
- **GET `/api/available-models`**: Lists dynamically available Gemini models for the current API Key.

## Configuration

Environment variables are managed via a `.env` file in the `backend/` directory:
- `GOOGLE_API_KEY`: Required for interacting with the Gemini model.
- `BRAVE_API_KEY`: Optional, for Brave Search.
- `ENABLE_GOOGLE_GROUNDING`: Toggle for native grounding (`true`/`false`).

## Running the Backend

```bash
cd backend
python -m app.main
```
This starts the FastAPI server on `0.0.0.0:8231` with auto-reload enabled.
