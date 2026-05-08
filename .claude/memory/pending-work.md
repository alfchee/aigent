# NaviBot 2.0 — Pending Work & Known Issues

Use this file to track work-in-progress items, known bugs, and future plans
that Claude should be aware of across sessions.

---

## Active / In-Progress

- MCP client integration — partial; see `plans/skills_mcp_reimplementation_plan.md`
- E2E Cypress tests excluded from CI (commented out in `ci.yml`) — not yet stable

## Known Issues

- `openviking` and `monty` are optional and not installed in CI; all tests that
  touch these must use stubs from `conftest.py`.
- WebSocket manager does not yet support horizontal scaling (single-process only).

## Backlog

- Add provider health-check endpoint (test connectivity with stored key).
- Implement semantic memory eviction policy (currently unbounded growth).
- Migrate `session_histories` (in-memory) to Redis for multi-process support.
- Enable Cypress E2E in CI once backend mock server is stable.
- Role-based skill filtering: enforce `allowed_skills` list from `roles.json` 
  in the supervisor routing logic.

## Completed Recently

- [2026-03] WebSocket reconnection with exponential backoff (frontend).
- [2026-03] Chat history pagination (IndexedDB + backend hybrid sync).
- [2026-03] Telegram webhook with MarkItDown media extraction pipeline.
- [2026-03] `ProviderConfigService` with Fernet encryption.
- [2026-03] Scheduler jobs persisted to SQLite (survive restarts).
