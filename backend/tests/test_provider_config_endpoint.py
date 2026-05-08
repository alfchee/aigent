"""
Tests for /config/providers endpoints.

Covers:
- GET /config/providers — list all providers with status
- PUT /config/providers — update one field without wiping others
- PUT /config/providers — explicit null clears a key
- POST /config/providers/{name}/test — mocked LLM call
- POST /config/providers/{name}/test — unknown provider returns 404
- GET /config/providers/{name}/models — cloud provider returns hardcoded list
- GET /config/providers/{name}/models — unknown provider returns 404
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KNOWN_PROVIDER_NAMES = {"gemini", "openai", "anthropic", "groq", "mistral", "ollama"}


# ---------------------------------------------------------------------------
# GET /config/providers
# ---------------------------------------------------------------------------


def test_get_providers_returns_all_known():
    response = client.get("/config/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    names = {p["name"] for p in data["providers"]}
    assert names == KNOWN_PROVIDER_NAMES


def test_get_providers_shape():
    response = client.get("/config/providers")
    data = response.json()
    for p in data["providers"]:
        assert "name" in p
        assert "label" in p
        assert "status" in p
        assert p["status"] in ("configured", "missing", "untested")
        assert "has_key" in p
        assert isinstance(p["has_key"], bool)
        assert "needs_key" in p
        # Keys are never returned in plain text
        assert "api_key" not in p


# ---------------------------------------------------------------------------
# PUT /config/providers
# ---------------------------------------------------------------------------


def test_update_one_field_does_not_wipe_others(tmp_path):
    """
    Setting only api_key must not clear base_url / default_model and vice-versa.
    Uses a temporary providers.json via monkeypatching workspace_config_dir.
    """
    providers_file = tmp_path / "providers.json"
    # Pre-populate with a base_url and default_model for ollama
    initial = [
        {
            "name": "ollama",
            "api_key": None,
            "base_url": "http://localhost:11434",
            "default_model": "llama3",
        }
    ]
    providers_file.write_text(json.dumps(initial))

    with patch(
        "app.core.provider_config.workspace_config_dir", return_value=tmp_path
    ):
        # Reset singleton so it reloads from our tmp file
        import app.core.provider_config as pc_module

        pc_module._instance = None

        # Update only default_model — base_url must survive
        response = client.put(
            "/config/providers",
            json={"providers": [{"name": "ollama", "default_model": "mistral"}]},
        )
        assert response.status_code == 200

        # Verify in persisted file
        stored = json.loads(providers_file.read_text())
        ollama = next((e for e in stored if e["name"] == "ollama"), None)
        assert ollama is not None
        assert ollama["base_url"] == "http://localhost:11434", "base_url was wiped"
        assert ollama["default_model"] == "mistral"

        # Cleanup singleton
        pc_module._instance = None


def test_explicit_null_api_key_clears_key(tmp_path):
    """
    Sending api_key=null explicitly must clear a stored key.
    """
    providers_file = tmp_path / "providers.json"
    initial = [
        {
            "name": "openai",
            "api_key": "encrypted-placeholder",
            "base_url": None,
            "default_model": None,
        }
    ]
    providers_file.write_text(json.dumps(initial))

    with patch(
        "app.core.provider_config.workspace_config_dir", return_value=tmp_path
    ):
        import app.core.provider_config as pc_module

        pc_module._instance = None

        response = client.put(
            "/config/providers",
            json={"providers": [{"name": "openai", "api_key": None}]},
        )
        assert response.status_code == 200

        stored = json.loads(providers_file.read_text())
        openai_entry = next((e for e in stored if e["name"] == "openai"), None)
        assert openai_entry is not None
        assert openai_entry["api_key"] is None, "api_key was not cleared"

        pc_module._instance = None


def test_response_never_exposes_plaintext_key(tmp_path):
    providers_file = tmp_path / "providers.json"
    providers_file.write_text(json.dumps([]))

    with patch(
        "app.core.provider_config.workspace_config_dir", return_value=tmp_path
    ):
        import app.core.provider_config as pc_module

        pc_module._instance = None

        response = client.put(
            "/config/providers",
            json={"providers": [{"name": "openai", "api_key": "sk-supersecret"}]},
        )
        assert response.status_code == 200
        data = response.json()
        raw_text = json.dumps(data)
        assert "sk-supersecret" not in raw_text, "Plaintext key returned in response"

        pc_module._instance = None


# ---------------------------------------------------------------------------
# POST /config/providers/{name}/test
# ---------------------------------------------------------------------------


def test_test_provider_unknown_returns_404():
    response = client.post("/config/providers/nonexistent/test")
    assert response.status_code == 404


def test_test_provider_no_key_returns_failure():
    """Without a configured key, cloud providers should return success=False."""
    with patch.dict(os.environ, {}, clear=False):
        # Ensure no key in env
        env_without_key = {
            k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"
        }
        with patch.dict(os.environ, env_without_key, clear=True):
            import app.core.provider_config as pc_module

            pc_module._instance = None
            response = client.post("/config/providers/openai/test")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            pc_module._instance = None


@pytest.mark.asyncio
async def test_test_provider_mocked_llm_call():
    """
    With a key configured, the test endpoint calls the LLM and returns success.
    The LLM call is mocked to avoid real network traffic.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hi"
    mock_response.choices[0].message.tool_calls = None

    with (
        patch(
            "app.core.provider_config.workspace_config_dir",
            return_value=Path(tempfile.mkdtemp()),
        ),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}),
        patch(
            "app.core.llm.acompletion",
            new=AsyncMock(return_value=mock_response),
        ),
    ):
        import app.core.provider_config as pc_module
        import app.core.llm as llm_module

        pc_module._instance = None
        llm_module.default_llm._provider_keys = {}

        response = client.post("/config/providers/openai/test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["latency_ms"] is not None

        pc_module._instance = None


# ---------------------------------------------------------------------------
# GET /config/providers/{name}/models
# ---------------------------------------------------------------------------


def test_get_models_known_cloud_provider():
    response = client.get("/config/providers/openai/models")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert isinstance(data["models"], list)
    assert len(data["models"]) > 0
    assert "gpt-4o-mini" in data["models"]


def test_get_models_unknown_provider():
    response = client.get("/config/providers/nonexistent/models")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_ollama_models_mocked():
    """Ollama models are fetched live from localhost:11434/api/tags."""
    mock_tags = {"models": [{"name": "llama3"}, {"name": "mistral"}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_tags
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.get("/config/providers/ollama/models")
        assert response.status_code == 200
        data = response.json()
        assert set(data["models"]) == {"llama3", "mistral"}
