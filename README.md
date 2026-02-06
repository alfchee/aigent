# Navibot 🚀

Navibot is an autonomous agentic framework designed to handle browser interactions, task scheduling, and real-time AI assistance. It features a robust FastAPI backend powered by Google Gemini and a sleek, responsive dashboard built with Vite and Vue 3.

## 🏗 Project Structure

```text
navibot/
├── backend/                # FastAPI Application
│   ├── app/                # Core logic & skills
│   ├── tests/              # Backend test suite
│   └── requirements.txt    # Python dependencies
├── frontend/               # Vite + Vue 3 Dashboard
│   ├── src/                # Vue components & assets
│   └── package.json        # Node.js dependencies
└── docs/                   # Project documentation & plans
```

## ✨ Features

- **Autonomous Agent**: Powered by **Gemini 2.0 Flash** for intelligent decision-making and tool use.
- **Browser Automation**: Integrated **Playwright** skills for web interaction.
- **Persistent Scheduling**: Robust task scheduling with **APScheduler** and **SQLAlchemy** (SQLite) to ensure tasks survive restarts.
- **Modern Dashboard**: Real-time chat interface with **Tailwind CSS** and dark mode support.
- **Developer Friendly**: Non-interactive setup and clear architecture.

## 🚀 Getting Started

### Prerequisites

- **Node.js**: v20.9.0+
- **Python**: v3.12+
- **Google Gemini API Key**: [Get one here](https://aistudio.google.com/app/apikey)

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

## 🛠 Running the Project

### Start the Backend
```bash
cd backend
# With venv activated
uvicorn app.main:app --reload --port 8231
```

### Start the Frontend
```bash
cd frontend
npm run dev
```
The dashboard will be available at [http://localhost:5174](http://localhost:5174).

## 🧰 Tech Stack

- **Backend**: FastAPI, Google GenAI SDK, Playwright, APScheduler, SQLAlchemy.
- **Frontend**: Vite, Vue 3, Tailwind CSS, TypeScript.
- **Database**: SQLite (for scheduling persistence).

## 📄 Documentation

Check the `/docs` directory for:
- [Work Plan](docs/work_plan.md)
- [Project Status](docs/project_status.md)
- [Implementation Plans](docs/implementation_plan.md)

---
Developed with ❤️ by the Navibot Team.
