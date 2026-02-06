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

### 2. Scheduler Service (`app/core/scheduler_service.py`)
Provides persistent job scheduling using **APScheduler** and **SQLAlchemy**.

#### Persistence
- **Database**: Uses `scheduler.db` (SQLite) to store job metadata.
- **Reliability**: Jobs survive server restarts. If the server is down when a job was supposed to run, it will typically execute upon startup (depending on misfire parameters).

#### Job Types
- **Date-based**: One-off execution at a specific ISO timestamp (`YYYY-MM-DD HH:MM:SS`).
- **Interval-based**: Recurring execution every $N$ seconds.

#### Execution Lifecycle
1. The scheduler monitors the database for due jobs.
2. When a job triggers, it calls `execute_agent_task(prompt)`.
3. This function:
    - Prints an execution log.
    - Instantiates a **fresh** `NaviBot` instance.
    - Sends the `prompt` to the agent.
    - Logs the final response from the AI.

---

## API Endpoints

The backend runs on port **8231** by default.

### Health Check
- **GET `/`**: Returns the status and version of the API.

### Chat Interface
- **POST `/api/chat`**: Sends a message to the NaviBot agent.
    - **Request Body**: `{"message": "string"}`
    - **Response**: `{"response": "string"}`

## Skills and Tools

The agent has access to several specialized skills:

| Skill | Tools Provided | Description |
| :--- | :--- | :--- |
| **System** | `list_files`, `read_file`, `create_file` | Basic filesystem operations. |
| **Browser** | `navigate`, `get_page_content`, `screenshot`, `close_browser` | Web automation and content extraction. |
| **Scheduler** | `schedule_task`, `schedule_interval_task` | Ability for the agent to schedule its own future tasks. |
| **Workspace** | `create_doc`, `send_email`, `create_calendar_event` | Placeholders for Google Workspace integrations. |

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
