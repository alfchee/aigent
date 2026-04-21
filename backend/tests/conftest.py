"""
Conftest: stub optional third-party modules not installed in the test environment.

These modules are used in app/core/agent_graph.py's import chain but are not
installed in CI. This conftest stubs them at sys.modules level so that imports
don't fail at test collection time.

Optional modules:
- openviking: memory backend (not in CI)
- monty: JSON utilities (not in CI)
"""
import sys
from unittest.mock import MagicMock


def _create_stub_module(name: str) -> MagicMock:
    """Create a minimal stub module that can be imported."""
    stub = MagicMock()
    stub.__name__ = name
    stub.__spec__ = None
    return stub


# Stub openviking (optional memory backend)
if "openviking" not in sys.modules:
    openviking_stub = _create_stub_module("openviking")
    openviking_stub.OpenViking = MagicMock()
    sys.modules["openviking"] = openviking_stub

# Stub monty and monty.json (optional JSON utilities)
if "monty" not in sys.modules:
    monty_stub = _create_stub_module("monty")
    monty_json_stub = _create_stub_module("monty.json")
    monty_json_stub.jsanitize = lambda x, **kwargs: x
    monty_stub.json = monty_json_stub
    sys.modules["monty"] = monty_stub
    sys.modules["monty.json"] = monty_json_stub
