# 🤖 Navibot

**Navibot** is an intelligent, AI-powered assistant designed to automate your daily workflows by integrating deeply with **Google Workspace**. It acts as a bridge between natural language instructions and your productivity tools, allowing you to manage files, schedule events, and process data through a simple chat interface (via Telegram).

Built with a robust **Python backend** and powered by **LLMs (Large Language Models)**, Navibot employs a **ReAct (Reason + Act)** cognitive loop to autonomously plan and execute complex tasks.

---

## 🚀 Key Features

- **🧠 Intelligent Agent:** Uses advanced LLMs to understand intent, break down complex requests, and reason through multi-step tasks.
- **📂 Google Drive Integration:**
  - List, search, and organize files and folders.
  - Move files between directories.
  - Download files for local processing (with auto-conversion for Google Docs/Sheets).
- **dV Google Calendar Management:**
  - Retrieve upcoming events and daily schedules.
  - Create and schedule new meetings and events intelligently.
- **📊 Google Sheets Automation:**
  - Create new spreadsheets from scratch.
  - Populate and update sheets with structured data.
- **💾 Long-term Memory:**
  - Vector-based memory system (ChromaDB) to retain user preferences, past interactions, and important context.
- **🐍 Secure Code Execution:**
  - Sandboxed Python environment to perform calculations, data analysis, and logic processing on the fly.
- **💬 Telegram Interface:**
  - Native integration with Telegram for a seamless, mobile-friendly user experience.

---

## 🛠️ Available Skills

Navibot comes equipped with a suite of "skills" (tools) that the AI agent can invoke to fulfill your requests:

| Category | Skill Name | Description |
|----------|------------|-------------|
| **Drive** | `list_drive_files` | Lists contents of a specific folder. |
| | `search_drive` | Searches for files/folders by name. |
| | `move_drive_file` | Moves a file to a target folder. |
| | `download_file_from_drive` | Downloads a file to the workspace (supports PDF, xlsx export). |
| **Calendar** | `list_upcoming_events` | Fetches upcoming calendar events. |
| | `create_calendar_event` | Creates a new event in the calendar. |
| **Sheets** | `create_google_sheet` | Creates a new Google Sheet. |
| | `update_sheet_data` | Writes data to a specific range in a Sheet. |
| **System** | `execute_python` | Runs Python code for calculation/processing. |
| | `read_file` | Reads the content of a local file. |
| | `memory_manager` | Stores/retrieves user-specific facts and context. |
| | `scheduler` | Schedules recurring background tasks. |

---

## ⚡ Getting Started

### Prerequisites

- **Python 3.10+**
- **Google Cloud Project** with Drive, Calendar, and Sheets APIs enabled.
- **Telegram Bot Token** (via @BotFather).
- **LLM API Key** (e.g., OpenAI, Gemini, etc., depending on configuration).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/navibot.git
    cd navibot
    ```

2.  **Set up the Backend:**
    The core logic resides in the `backend` directory. Follow the detailed setup guide there.
    
    👉 **[Read the Backend Documentation](backend/README.md)**

3.  **Configure Credentials:**
    -   Place your `google_service.json` (Service Account) or OAuth credentials in `backend/app/core/credentials/`.
    -   Create a `.env` file with your API keys.

4.  **Run the Bot:**
    ```bash
    cd backend
    uvicorn app.main:app --reload
    ```

---

## ⚙️ Configuration

The application is highly configurable via `backend/app/core/config_manager.py` and environment variables. Key configurations include:

-   **Model Selection:** Choose between different LLM models (e.g., Gemini Pro, Flash).
-   **Auth Mode:** Switch between `service_account` (server-side) and `oauth` (user-consent) for Google Workspace.
-   **Memory Settings:** Configure the persistence path for ChromaDB.

For more details, check the **[Backend README](backend/README.md)**.

---

## 🧪 Testing

To ensure everything is working correctly, you can run the included test suite:

```bash
# Run all tests
cd backend
python -m unittest discover tests
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
