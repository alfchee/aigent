import pytest
from app.memory.openviking_store import MemoryController, OpenVikingConfig
from unittest.mock import MagicMock, patch

# Mock OpenViking client
@pytest.fixture
def mock_openviking():
    with patch("app.memory.openviking_store.OpenViking") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.mkdir = MagicMock()
        mock_instance.add_resource = MagicMock(return_value={"status": "ok"})
        search_result = MagicMock()
        search_result.memories = [MagicMock(content="User likes Python")]
        search_result.resources = [MagicMock(content="User is building a bot")]
        search_result.skills = []
        search_result.query_results = []
        mock_instance.search = MagicMock(return_value=search_result)
        yield mock_instance

def test_openviking_initialization(mock_openviking):
    config = OpenVikingConfig(
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_api_key="test-key",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_api_key="test-key"
    )
    
    controller = MemoryController(user_id="test_user", config=config)
    assert controller.ov_client is not None

def test_add_fact(mock_openviking):
    controller = MemoryController(user_id="test_user")
    controller.add_fact("I love coding", "facts/hobbies.md")
    mock_openviking.add_resource.assert_called_once()
    kwargs = mock_openviking.add_resource.call_args.kwargs
    assert kwargs["to"] == "/user/test_user/facts/hobbies.md"
    assert kwargs["wait"] is True

def test_retrieve_context(mock_openviking):
    controller = MemoryController(user_id="test_user")
    context = controller.retrieve_context("What do I like?")
    assert "User likes Python" in context
    assert "User is building a bot" in context
    mock_openviking.search.assert_called_with(
        query="What do I like?",
        target_uri="/user/test_user",
        limit=5,
    )

def test_save_session_summary(mock_openviking):
    controller = MemoryController(user_id="test_user")
    controller.save_session_summary("sess_123", "User discussed Python.")
    kwargs = mock_openviking.add_resource.call_args.kwargs
    assert kwargs["to"] == "/user/test_user/sessions/sess_123/summary.md"
