import pytest
from app.skills.web_browse import web_browse, WebBrowseArgs, WebBrowseResult
from app.skills.smart_search import smart_search, SmartSearchArgs, SmartSearchResult
from app.skills.file_tools import (
    list_artifacts,
    read_artifact,
    ListArtifactsResult,
    ReadArtifactResult,
)
from app.skills.registry import registry


def test_web_browse_unsupported_scheme():
    result = web_browse("ftp://example.com")
    parsed = WebBrowseResult.model_validate_json(result)
    assert parsed.error is not None
    assert "Unsupported" in parsed.error


def test_web_browse_invalid_url():
    result = web_browse("not-a-url")
    parsed = WebBrowseResult.model_validate_json(result)
    assert parsed.error is not None


def test_smart_search_empty_query():
    result = smart_search("")
    parsed = SmartSearchResult.model_validate_json(result)
    assert parsed.error is not None


def test_smart_search_returns_results():
    result = smart_search("python language", num_results=3)
    parsed = SmartSearchResult.model_validate_json(result)
    assert parsed.error is None
    assert len(parsed.results) <= 3
    assert all("url" in r for r in parsed.results)


def test_smart_search_args_validation():
    args = SmartSearchArgs(query="test")
    assert args.num_results == 5
    assert args.search_type == "web"


def test_list_artifacts_unknown_session(tmp_path, monkeypatch):
    import app.skills.file_tools as ft

    monkeypatch.setattr(ft, "WORKSPACE_SESSIONS", tmp_path)
    result = list_artifacts("nonexistent_session_xyz")
    parsed = ListArtifactsResult.model_validate_json(result)
    assert parsed.session_id == "nonexistent_session_xyz"
    assert parsed.artifacts == []
    assert parsed.error is None


def test_read_artifact_not_found(tmp_path, monkeypatch):
    import app.skills.file_tools as ft

    monkeypatch.setattr(ft, "WORKSPACE_SESSIONS", tmp_path)
    result = read_artifact("session_x", "missing.txt")
    parsed = ReadArtifactResult.model_validate_json(result)
    assert parsed.error is not None
    assert "not found" in parsed.error.lower()


def test_read_artifact_success(tmp_path, monkeypatch):
    import app.skills.file_tools as ft

    session_dir = tmp_path / "test_session" / "artifacts"
    session_dir.mkdir(parents=True)
    (session_dir / "report.txt").write_text("Hello from artifact", encoding="utf-8")
    monkeypatch.setattr(ft, "WORKSPACE_SESSIONS", tmp_path)
    result = read_artifact("test_session", "report.txt")
    parsed = ReadArtifactResult.model_validate_json(result)
    assert parsed.error is None
    assert "Hello from artifact" in parsed.content


def test_registry_has_all_new_tools():
    assert registry.get_tool("web_browse") is not None
    assert registry.get_tool("smart_search") is not None
    assert registry.get_tool("list_artifacts") is not None
    assert registry.get_tool("read_artifact") is not None
