# NaviBot 2.0 — Architecture Decisions Log

Record significant architecture decisions here so Claude has context across sessions.

---

## [2026-03] Phoenix Reboot

- **Decision**: Moved from custom orchestrator to LangGraph Supervisor-Worker topology.
- **Rationale**: Cleaner routing, built-in state management, easier to extend workers.
- **Impact**: `agent_graph.py` is the single source of truth for the agent flow.

## [2026-03] LiteLM as LLM abstraction

- **Decision**: All LLM calls routed through LiteLM (`app/core/llm.py`).
- **Rationale**: Single API for Gemini, OpenAI, Anthropic, and local models.
- **Impact**: Provider switching is runtime-configurable; no code changes needed.

## [2026-03] Fernet-encrypted provider keys

- **Decision**: API keys stored encrypted in `workspace/config/providers.json`.
- **Rationale**: Keys must not appear in plaintext in config files or logs.
- **Impact**: `ProviderConfigService.get_key()` decrypts on read; REST API only
  exposes `has_key: bool`.

## [2026-03] OpenViking for semantic memory

- **Decision**: `openviking` used as the vector DB for semantic memory layer.
- **Rationale**: Lightweight, file-based, no external service required.
- **Impact**: `openviking` is an optional dep — tests stub it via `conftest.py`.

## [2026-03] Monty for sandbox policy validation

- **Decision**: `monty` used inside `SecureSandbox` for JSON/policy validation.
- **Rationale**: Lightweight, already in the data-science stack.
- **Impact**: `monty` is an optional dep — tests stub it via `conftest.py`.

## [2026-03] Workspace data directory

- **Decision**: All runtime data (SQLite, sessions, config) lives under `workspace/`.
- **Rationale**: Single Docker volume mount; clean separation from source code.
- **Impact**: Always use `app.core.paths` helpers, never hardcode paths.

## [2026-03] Optional deps CI strategy

- **Decision**: `openviking` and `monty` are NOT installed in CI.
- **Rationale**: Reduces CI complexity; these are optional backends.
- **Impact**: `conftest.py` stubs them at `sys.modules` level before test collection.
