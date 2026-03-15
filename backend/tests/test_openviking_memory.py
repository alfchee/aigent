import pytest
from app.memory.openviking_store import MemoryController, OpenVikingConfig
from unittest.mock import MagicMock, patch

# Mock OpenViking client
@pytest.fixture
def mock_openviking():
    with patch("app.memory.openviking_store.OpenViking") as MockClient:
        mock_instance = MockClient.return_value
        # Mock methods we expect to use
        mock_instance.add_file = MagicMock()
        mock_instance.retrieve.return_value = [
            MagicMock(content="User likes Python"),
            MagicMock(content="User is building a bot")
        ]
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
    
    # We expect `add_file` to be called with a specific path
    controller.add_fact("I love coding", "facts/hobbies.md")
    
    mock_openviking.add_file.assert_called_with(
        path="test_user/facts/hobbies.md", 
        content="I love coding"
    )

def test_retrieve_context(mock_openviking):
    controller = MemoryController(user_id="test_user")
    
    context = controller.retrieve_context("What do I like?")
    
    assert "User likes Python" in context
    assert "User is building a bot" in context
    
    mock_openviking.retrieve.assert_called_with(
        query="What do I like?",
        path="test_user/",
        top_k=5
    )

def test_save_session_summary(mock_openviking):
    controller = MemoryController(user_id="test_user")
    
    controller.save_session_summary("sess_123", "User discussed Python.")
    
    mock_openviking.add_file.assert_called_with(
        path="test_user/sessions/sess_123/summary.md",
        content="User discussed Python."
    )
