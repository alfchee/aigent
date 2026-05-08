# NaviBot 2.0 — Testing Patterns & Gotchas

Reference for writing and debugging tests in this project.

---

## Pytest Setup

- Always run from `backend/` with `PYTHONPATH=.`:
  ```bash
  cd backend && PYTHONPATH=. python -m pytest tests -v -m "not network"
  ```
- `conftest.py` stubs `openviking` and `monty` before test collection.
- Async tests use `@pytest.mark.asyncio` (from `pytest-asyncio`).

## Marking Tests

```python
import pytest

@pytest.mark.network   # requires real API keys / internet
async def test_real_llm_call():
    ...
```

CI always runs with `-m "not network"` — unmarked tests that hit external
services will break CI.

## Stubbing Optional Deps

If your test file imports a module that transitively imports `openviking` or
`monty`, ensure those stubs are present.  `conftest.py` handles it globally,
but if you need a custom mock in a specific test:

```python
from unittest.mock import MagicMock, patch

with patch("app.memory.openviking_store.OpenViking") as mock_ov:
    mock_ov.return_value = MagicMock()
    # ... test body
```

## FastAPI / WebSocket Testing

- Use `httpx.AsyncClient` with `app` as the ASGI transport for HTTP endpoints.
- Use `fastapi.testclient.TestClient` for synchronous WebSocket testing.
- See `tests/test_websocket_manager.py` for WebSocket test patterns.

## Common Fixtures (conftest.py)

- No shared fixtures yet beyond the module stubs.  Add project-wide fixtures
  to `conftest.py`; test-local fixtures go in the individual test file.

## Frontend Tests

- Vitest unit tests live in `frontend/src/test/`.
- Mock API calls with `vi.mock('...service')` or MSW handlers.
- Pinia stores should be tested with `setActivePinia(createPinia())` in setup.
