"""
Conftest: stub optional third-party modules that are not installed in the
test environment so that tests importing app.core.agent_graph don't fail at
collection time.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock


def _stub(name: str) -> MagicMock:
    mod = MagicMock()
    mod.__name__ = name
    mod.__spec__ = None
    sys.modules[name] = mod
    return mod


# Stub optional third-party packages not installed in CI
if "openviking" not in sys.modules:
    ov = _stub("openviking")
    ov.OpenViking = MagicMock()

if "monty" not in sys.modules:
    monty = _stub("monty")
    monty_json = _stub("monty.json")
    monty_json.jsanitize = lambda x, **kw: x
    monty.json = monty_json
