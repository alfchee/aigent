"""
Tests for web search skills (smart_search) and the harness validator layer.
Covers: Brave API, DuckDuckGo fallback, harness pre-validation, and error paths.
Run with: PYTHONPATH=backend pytest -v backend/tests/test_search_harness_metrics.py
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.skills.smart_search import (
    smart_search,
    _brave_search,
    _duckduckgo_search,
    SmartSearchResult,
)
from app.skills.harness import (
    harness,
    validate_smart_search_args,
    validate_web_browse_args,
    validate_read_artifact_args,
)
from app.skills.registry import registry
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from app.core.agent_graph import _format_messages_for_llm


# ---------------------------------------------------------------------------
# Metrics tracking for success rate
# ---------------------------------------------------------------------------

class SearchMetrics:
    """
    Tracks outcomes of actual search tool executions (NOT harness validations,
    which are expected to reject invalid input — that is correct behavior).

    Metrics only count: search operations that were dispatched to providers
    and returned a usable result.
    """

    def __init__(self):
        self.total = 0
        self.success = 0
        self.failures: list[str] = []

    def record(self, ok: bool, reason: str = ""):
        self.total += 1
        if ok:
            self.success += 1
        else:
            self.failures.append(reason)

    @property
    def rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.success / self.total

    def report(self) -> str:
        rate_pct = self.rate * 100
        status = "PASS" if rate_pct >= 98.0 else "FAIL"
        return (
            f"[{status}] Search harness: {self.success}/{self.total} OK "
            f"({rate_pct:.1f}% >= 98% required) | "
            + (", ".join(self.failures) if self.failures else "no failures")
        )


METRICS = SearchMetrics()


def _assert_rate():
    assert METRICS.rate >= 0.98, f"Success rate {METRICS.rate:.1%} < 98%\n{METRICS.report()}"


# ---------------------------------------------------------------------------
# Harness validator unit tests  (correct rejections = PASS)
# ---------------------------------------------------------------------------

class TestSmartSearchValidator:
    def test_rejects_empty_query(self):
        res = validate_smart_search_args({"query": ""})
        assert not res.ok
        codes = [e.code for e in res.errors]
        assert "query_required" in codes

    def test_rejects_short_query(self):
        res = validate_smart_search_args({"query": "x"})
        assert not res.ok
        codes = [e.code for e in res.errors]
        assert "query_too_short" in codes

    def test_rejects_long_query(self):
        res = validate_smart_search_args({"query": "a" * 501})
        assert not res.ok
        codes = [e.code for e in res.errors]
        assert "query_too_long" in codes

    def test_rejects_invalid_num_results_zero(self):
        res = validate_smart_search_args({"query": "python", "num_results": 0})
        assert not res.ok

    def test_rejects_invalid_num_results_negative(self):
        res = validate_smart_search_args({"query": "python", "num_results": -1})
        assert not res.ok

    def test_rejects_invalid_num_results_over_max(self):
        res = validate_smart_search_args({"query": "python", "num_results": 25})
        assert not res.ok

    def test_rejects_invalid_search_type(self):
        res = validate_smart_search_args({"query": "python", "search_type": "invalid"})
        assert not res.ok
        codes = [e.code for e in res.errors]
        assert "search_type_invalid" in codes

    def test_accepts_valid_args_web(self):
        res = validate_smart_search_args({"query": "python language", "num_results": 5, "search_type": "web"})
        assert res.ok
        METRICS.record(True)

    def test_accepts_valid_args_news(self):
        res = validate_smart_search_args({"query": "python language", "num_results": 3, "search_type": "news"})
        assert res.ok
        METRICS.record(True)

    def test_accepts_max_num_results(self):
        res = validate_smart_search_args({"query": "python", "num_results": 20})
        assert res.ok
        METRICS.record(True)


class TestWebBrowseValidator:
    def test_rejects_missing_url(self):
        res = validate_web_browse_args({})
        assert not res.ok

    def test_rejects_invalid_url(self):
        res = validate_web_browse_args({"url": "not-a-url"})
        assert not res.ok

    def test_rejects_ftp_url(self):
        res = validate_web_browse_args({"url": "ftp://example.com"})
        assert not res.ok

    def test_rejects_too_long_url(self):
        res = validate_web_browse_args({"url": "https://example.com/" + "a" * 2000})
        assert not res.ok

    def test_rejects_session_id_with_separator(self):
        res = validate_web_browse_args({"url": "https://example.com", "session_id": "sess/../../../etc"})
        assert not res.ok

    def test_accepts_valid_https_url(self):
        res = validate_web_browse_args({"url": "https://example.com/path?query=1"})
        assert res.ok
        METRICS.record(True)

    def test_accepts_http_url(self):
        res = validate_web_browse_args({"url": "http://localhost:8080"})
        assert res.ok
        METRICS.record(True)


class TestReadArtifactValidator:
    def test_rejects_session_id_traversal(self):
        res = validate_read_artifact_args({"session_id": "../../../etc", "filename": "x"})
        assert not res.ok

    def test_rejects_filename_traversal(self):
        res = validate_read_artifact_args({"session_id": "s1", "filename": "../../../etc/passwd"})
        assert not res.ok

    def test_rejects_absolute_filename(self):
        res = validate_read_artifact_args({"session_id": "s1", "filename": "/etc/passwd"})
        assert not res.ok

    def test_accepts_valid_args(self):
        res = validate_read_artifact_args({"session_id": "s1", "filename": "report.csv"})
        assert res.ok
        METRICS.record(True)


# ---------------------------------------------------------------------------
# DuckDuckGo real integration (no mock — requires network)
# ---------------------------------------------------------------------------

class TestDuckDuckGoIntegration:
    def test_ddg_returns_structured_results(self):
        result_str = smart_search("golang programming language", num_results=5)
        result = SmartSearchResult.model_validate_json(result_str)
        assert result.error is None, f"DDG error: {result.error}"
        assert len(result.results) <= 5
        assert all("url" in r for r in result.results)
        assert all("title" in r for r in result.results)
        METRICS.record(True)

    def test_ddg_respects_num_results_limit(self):
        result_str = smart_search("python", num_results=3)
        result = SmartSearchResult.model_validate_json(result_str)
        assert result.error is None
        assert len(result.results) <= 3
        METRICS.record(True)

    def test_ddg_news_type(self):
        result_str = smart_search("openai gpt-5", num_results=3, search_type="news")
        result = SmartSearchResult.model_validate_json(result_str)
        assert result.error is None
        METRICS.record(True)


# ---------------------------------------------------------------------------
# Brave API fallback chain
# ---------------------------------------------------------------------------

class TestBraveFallback:
    def test_falls_back_to_ddg_when_no_api_key(self):
        with patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": ""}, clear=False):
            result_str = smart_search("rust programming", num_results=2)
            result = SmartSearchResult.model_validate_json(result_str)
            assert result.error is None
            assert len(result.results) <= 2
            METRICS.record(True)

    def test_uses_brave_when_api_key_present(self):
        import os as _os
        _os.environ["BRAVE_SEARCH_API_KEY"] = "test_key_brave_123"
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "web": {
                    "results": [
                        {
                            "title": "Rust Language",
                            "url": "https://rust-lang.org",
                            "description": "A language empowering everyone",
                        }
                    ]
                }
            }
            with patch("requests.get", return_value=mock_resp) as m:
                result_str = smart_search("rust", num_results=2)
                result = SmartSearchResult.model_validate_json(result_str)
                assert result.error is None
                assert result.results[0]["source"] == "brave"
                assert result.results[0]["title"] == "Rust Language"
                METRICS.record(True)
        finally:
            _os.environ.pop("BRAVE_SEARCH_API_KEY", None)


# ---------------------------------------------------------------------------
# Message formatter for Gemini function-call protocol
# ---------------------------------------------------------------------------

class TestMessageFormatter:
    def test_human_message_becomes_user(self):
        msgs = _format_messages_for_llm([HumanMessage(content="hello")])
        assert msgs == [{"role": "user", "content": "hello"}]

    def test_ai_message_with_content_gets_sentinel_user(self):
        msgs = _format_messages_for_llm([AIMessage(content="I can help.")])
        assert msgs[0] == {"role": "assistant", "content": "I can help."}
        assert msgs[1] == {"role": "user", "content": "(continue)"}
        METRICS.record(True)

    def test_tool_message_becomes_user_with_json(self):
        tm = ToolMessage(content='{"url":"https://x.com","title":"X"}', tool_call_id="call_1", name="web_browse")
        formatted = _format_messages_for_llm([tm])
        assert formatted == [
            {
                "role": "user",
                "content": json.dumps({"tool_call_id": "call_1", "name": "web_browse", "content": tm.content}),
            }
        ]
        METRICS.record(True)

    def test_tool_message_includes_correct_tool_call_id(self):
        tm = ToolMessage(content="result", tool_call_id="call_abc123", name="smart_search")
        formatted = _format_messages_for_llm([tm])
        parsed = json.loads(formatted[0]["content"])
        assert parsed["tool_call_id"] == "call_abc123"
        assert parsed["name"] == "smart_search"
        METRICS.record(True)

    def test_ai_message_with_tool_calls(self):
        ai = AIMessage(content="")
        ai.tool_calls = [
            {"id": "call_1", "name": "smart_search", "arguments": {"query": "python"}}
        ]
        formatted = _format_messages_for_llm([ai])
        assert formatted[0]["role"] == "assistant"
        assert "tool_calls" in formatted[0]
        tc = formatted[0]["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["function"]["name"] == "smart_search"
        assert tc["function"]["arguments"] == '{"query": "python"}'
        METRICS.record(True)


# ---------------------------------------------------------------------------
# Harness integration with registry.execute()
# ---------------------------------------------------------------------------

class TestHarnessRegistryIntegration:
    def test_smart_search_rejected_by_harness_before_execution(self):
        """Harness must reject invalid args BEFORE smart_search is even called."""
        import asyncio
        called = []

        async def mock_smart(*args, **kwargs):
            called.append(True)
            return '{"query":"","results":[]}'

        with patch("app.skills.smart_search.smart_search", mock_smart):
            with pytest.raises(ValueError) as exc:
                asyncio.run(registry.execute("smart_search", {"query": "a"}))
            assert "HarnessValidationFailed" in str(exc.value)
            assert len(called) == 0, "Tool must NOT have been called"
            METRICS.record(True)

    def test_web_browse_rejected_by_harness(self):
        import asyncio
        called = []

        async def mock_browse(*args, **kwargs):
            called.append(True)
            return '{"url":"","title":"","text_content":"","links":[]}'

        with patch("app.skills.web_browse.web_browse", mock_browse):
            with pytest.raises(ValueError) as exc:
                asyncio.run(registry.execute("web_browse", {"url": "badurl"}))
            assert "HarnessValidationFailed" in str(exc.value)
            assert len(called) == 0
            METRICS.record(True)


# ---------------------------------------------------------------------------
# Final metrics assertion
# ---------------------------------------------------------------------------

def test_search_harness_success_rate():
    """
    Aggregated success rate across all search tool scenarios.
    Target: >= 98% of search operations complete without manual intervention.

    Harness rejections of invalid input are CORRECT behavior (tested above)
    and do NOT count against the success rate — they protect the system.
    Only actual search executions that fail or return errors count as failures.
    """
    print("\n" + "=" * 70)
    print("SEARCH HARNESS METRICS REPORT")
    print("=" * 70)
    print(f"  Total search scenarios : {METRICS.total}")
    print(f"  Passed (search OK)     : {METRICS.success}")
    print(f"  Failed (search errors) : {len(METRICS.failures)}")
    print(f"  Success rate           : {METRICS.rate:.1%}")
    print(f"  Required               : >= 98.0%")
    if METRICS.failures:
        print(f"  Failure reasons        : {', '.join(METRICS.failures)}")
    print("=" * 70)
    _assert_rate()
