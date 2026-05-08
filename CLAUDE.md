# NaviBot 2.0 (The Phoenix) — CLAUDE.md

Project-wide guidance for Claude. Read this first on every session.

---

## Project Overview

NaviBot 2.0 is a next-generation agentic chatbot ecosystem built on a
**Supervisor-Worker LangGraph topology**, multi-provider LLM support via
**LiteLM**, a three-layer memory system (**OpenViking**), and a unified tool
registry that bridges local skills with the **Model Context Protocol (MCP)**.

Interfaces: WebSocket (browser chat) + Telegram webhook.

---

## Repository Structure

```
/
├── backend/                   # Python FastAPI application
│   ├── app/
│   │   ├── main.py            # FastAPI entry point, WebSocket handler
│   │   ├── core/              # Agent graph, LLM, roles, provider config, memory
│   │   ├── api/               # FastAPI routers (sessions, config, roles, mcp, websockets, telegram)
│   │   ├── skills/            # Unified Tool Registry + skill implementations
│   │   ├── memory/            # MemoryController + episodic/semantic backends
│   │   ├── channels/          # Telegram bot channel adapter
│   │   ├── sandbox/           # SecureSandbox (Pydantic + Monty + resource limits)
│   │   └── middleware/        # Request middleware
│   ├── tests/                 # Pytest test suite
│   └── requirements.txt       # Python dependencies
├── frontend/                  # Vue 3 + Vite + TypeScript + Tailwind
│   └── src/
│       ├── pages/             # Route-level views
│       ├── components/        # Reusable UI components
│       ├── stores/            # Pinia stores
│       ├── services/          # API/WebSocket service layer
│       ├── composables/       # Vue composables
│       └── types/             # TypeScript type definitions
├── workspace/                 # Runtime data (Docker volume in production)
│   ├── config/                # roles.json, mcp_config.json, ov.conf, soul_prompt.txt
│   ├── db/                    # SQLite databases (chat_messages, episodic_memory, scheduler)
│   └── sessions/              # Per-session file downloads
├── data/                      # Static vector DB and Viking data
├── plans/                     # Architecture plans and roadmap documents
├── scripts/                   # Dev helper scripts
└── .github/workflows/         # CI (ci.yml, dev-tag.yml, main-release.yml)
```

---

## Development Commands

### Backend

```bash
# Start dev server (loads .env, sets PYTHONPATH, hot-reload)
./scripts/run-backend-dev.sh

# Or directly
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all backend tests (excludes network-dependent tests)
cd backend && PYTHONPATH=. python -m pytest tests -v -m "not network"

# Run a specific test file
cd backend && PYTHONPATH=. python -m pytest tests/test_provider_config_endpoint.py -v

# Run with network tests included (requires real API keys)
cd backend && PYTHONPATH=. python -m pytest tests -v

# Python syntax check (mirrors CI build step)
cd backend && python -m compileall app
```

### Frontend

```bash
cd frontend

npm run dev       # Vite dev server (hot-reload)
npm run build     # Production build
npm run lint      # ESLint check
npm test          # Vitest unit tests
npm run e2e       # Cypress end-to-end tests (requires running backend)
```

---

## Architecture & Key Patterns

### LangGraph Supervisor-Worker

- **Entry**: `app/core/agent_graph.py` — `get_graph()` returns the compiled graph.
- The supervisor routes messages to specialised worker nodes based on role hints
  (`@role_name` prefix in the user message, or the session's configured role).
- Workers share the same `ToolRegistry` instance.

### LLM Abstraction (LiteLM)

- `app/core/llm.py` — `default_llm` factory; every LLM call goes through LiteLM.
- Provider switching is done at runtime via `ProviderConfigService`
  (`app/core/provider_config.py`).  API keys are Fernet-encrypted at rest in
  `workspace/config/providers.json`.  **Never return plaintext keys from any
  API endpoint.**

### Memory (Three Layers)

| Layer | Class | Backing Store |
|-------|-------|---------------|
| Working (short-term) | `session_histories` dict in `main.py` | In-process memory |
| Episodic | `EpisodicMemory` (`app/memory/episodic.py`) | SQLite `episodic_memory.db` |
| Semantic | `SemanticMemory` (`app/memory/semantic.py`) | OpenViking vector DB |

`MemoryController` (`app/memory/controller.py`) unifies all three layers.
One controller instance per session, held in `session_memory` dict.

### Tool Registry & Skills

- `app/skills/registry.py` — `ToolRegistry` singleton (`registry`).
- Skills register with Pydantic input/output schemas.
- MCP tools are loaded from `workspace/config/mcp_config.json` via
  `MCPManager` (`app/core/mcp_client.py`).
- `app/skills/harness.py` — execution harness with metrics tracking.

### Chat Persistence

- `ChatPersistence` (`app/core/chat_persistence.py`) writes all messages to
  `workspace/db/chat_messages.db` (SQLite via aiosqlite).
- Sessions are identified by `session_id` (UUID).

### Roles

- `workspace/config/roles.json` — role definitions with system prompts and
  allowed skills.
- `RoleManager` (`app/core/roles.py`) supports hot-reload via
  `POST /roles/reload`.

### Sandbox

- `SecureSandbox` (`app/sandbox/e2b_sandbox.py`) — uses Monty for policy
  validation and `resource.setrlimit` for CPU/memory/file limits.
- Trigger via `/python` prefix or fenced ```python``` blocks in chat.

### WebSocket Protocol

Events sent from server to client:
- `ack` — message received
- `status` — processing step update
- `tool_call` — tool invocation trace
- `assistant_message` — final response chunk
- `error` — structured error payload
- `pong` — heartbeat response

---

## Testing Guidelines

### Backend Tests

- Located in `backend/tests/`.
- `conftest.py` stubs `openviking` and `monty` so tests run without those
  optional packages installed (CI-safe).
- Mark tests that need real network/API access with `@pytest.mark.network`.
- CI runs with `-m "not network"` — **never make unmarked tests hit external
  APIs**.
- Use `pytest-asyncio` for async test functions (`@pytest.mark.asyncio`).
- Prefer `unittest.mock` / `MagicMock` for external dependencies.

### Frontend Tests

- Unit tests: Vitest in `frontend/src/test/`.
- E2E: Cypress in `frontend/cypress/e2e/`.
- E2E tests are excluded from CI (`ci.yml` has them commented out).

### Adding a New Test

1. Create `backend/tests/test_<module>.py`.
2. Import the module under test.
3. Stub any optional third-party deps in the test file or `conftest.py`.
4. Mark network tests with `@pytest.mark.network`.

---

## CI/CD

Workflow files in `.github/workflows/`:

| File | Trigger | Purpose |
|------|---------|---------|
| `ci.yml` | PR → `dev`, `qa`, `reboot` | Lint + test + build (backend + frontend) |
| `dev-tag.yml` | Push tag `dev-*` | Dev image build |
| `main-release.yml` | Push to `main` | Production release |

CI steps (in order):
1. Python 3.12, Node 20 setup with caching.
2. `pip install -r backend/requirements.txt`
3. `PYTHONPATH=. pytest tests -v -m "not network"` (backend)
4. `python -m compileall app` (syntax check)
5. `npm install && npm run lint && npm test && npm run build` (frontend)

---

## Environment Variables

Copy `backend/.env.example` → `backend/.env` and fill in:

| Variable | Purpose |
|----------|---------|
| `AIGENT_SECRET` | Fernet key derivation for encrypted provider keys |
| `NAVIBOT_ENV` | `development` / `production` |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` |
| `GEMINI_API_KEY` | Google Gemini (optional, can be set via UI) |
| `OPENAI_API_KEY` | OpenAI (optional) |
| `ANTHROPIC_API_KEY` | Anthropic (optional) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_SECRET` | Webhook secret for signature validation |
| `HOST` | Uvicorn bind host (default `0.0.0.0`) |
| `PORT` | Uvicorn bind port (default `8000`) |

---

## Code Style & Conventions

### Python (Backend)

- **Python 3.11+** with `from __future__ import annotations`.
- Pydantic v2 models for all request/response schemas.
- `async`/`await` throughout — no synchronous blocking I/O on the event loop.
- Logging via `logging.getLogger("navibot.<module>")`.
- Paths resolved through `app.core.paths` helpers (`repo_root`,
  `workspace_db_dir`, `workspace_config_dir`) — never hardcode paths.
- Never log or return plaintext API keys.

### TypeScript / Vue (Frontend)

- Vue 3 Composition API (`<script setup>`).
- Pinia for global state (`frontend/src/stores/`).
- Tailwind CSS utility classes — no custom CSS unless necessary.
- Composables in `frontend/src/composables/` for reusable reactive logic.
- TypeScript strict mode — all props and emits typed.

---

## Security Rules (OWASP)

- **A02 Cryptographic Failures**: Provider API keys are encrypted with Fernet
  (`ProviderConfigService`).  Plaintext values never leave the server.
- **A03 Injection**: Telegram webhooks validated with HMAC secret header.
  Sandbox input validated through Pydantic + Monty before execution.
- **A05 Security Misconfiguration**: CORS origins must be explicit in
  production (not `*`).
- **A08 Integrity Failures**: Signed Telegram webhook secret enforced via
  `X-Telegram-Bot-Api-Secret-Token`.
- When adding new endpoints, always validate and sanitise inputs with Pydantic.

---

## Common Pitfalls

- **Missing PYTHONPATH**: Always run pytest from `backend/` with
  `PYTHONPATH=.` or set `PYTHONPATH=backend` from the root.
- **Optional deps**: `openviking` and `monty` are not installed in CI.
  Stub them in `conftest.py` if your test's import chain touches them.
- **Workspace paths**: Runtime data lives in `workspace/` (repo root) or
  `/workspace/` inside Docker. Use `app.core.paths` helpers.
- **Encrypted keys**: `ProviderConfigService.get_key()` returns the plaintext
  only internally. The REST API only exposes `has_key: bool`.
- **WebSocket reconnect**: The frontend handles reconnection with exponential
  backoff — don't implement custom reconnection logic in new components.

---

## Planning & Roadmap

Detailed plans live in `plans/`:

| File | Topic |
|------|-------|
| `phoenix_roadmap.md` | Overall phase-by-phase roadmap |
| `skills_mcp_reimplementation_plan.md` | MCP / skills integration |
| `memory_implementation_plan.md` | Memory layer design |
| `websocket_improvements_plan.md` | WebSocket protocol evolution |
| `frontend_backend_alignment_report_2026-03.md` | API contract audit |
| `session_persistence_and_fixes_summary.md` | Session/persistence notes |
