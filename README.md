# NaviBot 2.0 (The Phoenix) 🦅🔥

NaviBot 2.0 is a next-generation agentic ecosystem orchestrated by LangGraph, designed for modularity, security, and multi-provider LLM support.

## Architecture (The "Phoenix" Stack)

*   **Orchestrator**: [LangGraph](https://langchain-ai.github.io/langgraph/) (Supervisor-Worker topology)
*   **LLM Abstraction**: [LiteLM](https://docs.litellm.ai/) (Support for Gemini, OpenAI, Anthropic, Local)
*   **Memory**: OpinViking Layered Memory (Working, Episodic, Semantic)
*   **Tools**: Unified Tool Registry (MCP + Local Skills) with Pydantic validation
*   **Sandboxing/Guardrails**: Secure Code Execution (Pydantic + Monty)
*   **Interface**: WebSockets + Telegram

## Directory Structure

```
/workspace          # Runtime data (DB, sessions, config) - Docker Volume
backend/
  app/
    core/           # Core logic (Graph, LLM, Config)
    skills/         # Tool Registry & Implementations
    memory/         # Memory Controllers
    api/            # FastAPI Endpoints
  tests/            # Pytest suite
```

## Getting Started

### Prerequisites

*   Python 3.11+
*   Docker (optional, for sandbox/db)

### Installation

1.  **Clone and Clean**:
    (Project has been reset to Phoenix baseline)

2.  **Install Dependencies**:
    ```bash
    pip install -r backend/requirements.txt
    ```

3.  **Environment Setup**:
    Copy `.env.example` to `backend/.env` and configure your keys:
    ```bash
    cp backend/.env.example backend/.env
    ```

4.  **Run Backend**:
    ```bash
    cd backend
    uvicorn app.main:app --reload
    ```

### Development

*   **Run Tests**:
    ```bash
    PYTHONPATH=backend pytest backend/tests/
    ```

## Roadmap

*   [x] **Phase 1: Foundation** (LiteLM, LangGraph, Tool Registry)
*   [ ] **Phase 2: Memory & Sandboxing** (OpinViking, Pydantic/Monty)
*   [ ] **Phase 3: Roles & UI** (WebSockets, Telegram)

## License

Apache 2.0
