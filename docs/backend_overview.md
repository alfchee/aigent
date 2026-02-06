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
| **System** | `list_files`, `read_file`, `create_file` | Basic filesystem operations. |
| **Browser** | `navigate`, `get_page_content`, `screenshot`, `close_browser` | Web automation and content extraction. |
| **Scheduler** | `schedule_task`, `schedule_interval_task` | Ability for the agent to schedule its own future tasks. |
| **Workspace** | `create_doc`, `send_email`, `create_calendar_event` | Placeholders for Google Workspace integrations. |

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
