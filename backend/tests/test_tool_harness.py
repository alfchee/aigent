import pytest
from app.skills.registry import registry
from app.skills.harness import harness, HarnessResult, ValidationError
from app.skills.web_browse import web_browse
from app.skills.smart_search import smart_search


def test_harness_rejects_invalid_web_browse_url():
    with pytest.raises(ValueError) as exc:
        # This will trigger pre-validation failure in the harness inside registry.execute
        import asyncio

        asyncio.run(registry.execute("web_browse", {"url": "notaurl", "session_id": "s1"}))
    assert "HarnessValidationFailed" in str(exc.value)


def test_harness_accepts_valid_web_browse_url(monkeypatch):
    # Call the harness directly to verify acceptance
    res = harness.run("web_browse", {"url": "https://example.com", "session_id": "s1"})
    assert res.ok


def test_harness_rejects_smart_search_short_query():
    with pytest.raises(ValueError) as exc:
        import asyncio

        asyncio.run(registry.execute("smart_search", {"query": "x", "num_results": 2}))
    assert "HarnessValidationFailed" in str(exc.value)


def test_harness_accepts_smart_search_valid_args():
    res = harness.run("smart_search", {"query": "python", "num_results": 3, "search_type": "web"})
    assert res.ok
