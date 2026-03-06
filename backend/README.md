# Navibot Backend

The backend service for Navibot, an AI-powered assistant designed to automate Google Workspace tasks and interact via Telegram.

## Features

- **AI Agent:** Powered by LLMs to understand natural language instructions.
- **Google Workspace Integration:**
  - **Drive:** List, search, move, download, and manage files.
  - **Calendar:** List upcoming events, create new events.
  - **Sheets:** Create spreadsheets, update data.
  - **Auth:** Supports both Service Account and OAuth2 flows.
- **Memory System:** Vector-based memory (ChromaDB) for long-term context retention.
- **Channel Support:** Built-in Telegram bot integration.
- **Code Execution:** Sandboxed Python code execution for dynamic tasks.

## Project Structure

```
backend/app/
├── api/            # FastAPI endpoints (sessions, files, settings, etc.)
├── channels/       # Communication channels (Telegram, etc.)
├── core/           # Core logic (Agent, Config, Memory, Auth)
├── integrations/   # External service integrations
├── skills/         # Tool implementations available to the Agent
└── main.py         # Application entry point
```

## Setup & Installation

1.  **Prerequisites:**
    -   Python 3.10 or higher.
    -   `pip` package manager.

2.  **Install Dependencies:**
    Navigate to the `backend` directory and install the required packages:
    ```bash
    cd backend
    pip install -r requirements.txt
    ```

3.  **Environment Variables:**
    Create a `.env` file in the `backend` directory (or root) with the following keys:
    ```env
    # LLM Configuration (Example)
    OPENAI_API_KEY=your_api_key_here
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN=your_bot_token_here
    
    # Memory Configuration
    NAVIBOT_MEMORY_DIR=./navi_memory_db
    
    # Workspace Configuration
    WORKSPACE_ROOT=./workspace_data
    ```

4.  **Google Credentials:**
    -   Place your `google_service.json` or OAuth client secrets in `backend/app/core/credentials/`.
    -   Update `workspace_config.json` to select your auth mode (`service_account` or `oauth`).

## Running the Application

Start the FastAPI server using Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.
API Documentation (Swagger UI): `http://localhost:8000/docs`.

## Available Skills

The Agent is equipped with the following skills:

-   **Google Drive:**
    -   `list_drive_files`: List contents of a folder.
    -   `search_drive`: Find files by name.
    -   `move_drive_file`: Move files between folders.
    -   `download_file_from_drive`: Download files for local processing (supports auto-export for Docs/Sheets).
-   **Google Calendar:**
    -   `list_upcoming_events`: View schedule.
    -   `create_calendar_event`: Schedule meetings.
-   **Google Sheets:**
    -   `create_google_sheet`: Create new spreadsheets.
    -   `update_sheet_data`: Write data to sheets.
-   **Productivity:**
    -   `read_file`: Read local files (PDF, text).
    -   `web_search`: Search the internet (if enabled).
    -   `scheduler`: Schedule recurring tasks.
-   **System:**
    -   `execute_python`: Run Python code for calculations or data processing.
    -   `memory_manager`: Store and retrieve user preferences/facts.

## Testing

Run the test suite using `unittest` or `pytest`:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test
python -m unittest tests/skills/test_google_drive_export.py
```
