import pytest
import os
from unittest.mock import MagicMock, patch
from app.memory.semantic import SemanticMemory, SemanticMemoryConfig
from app.memory.episodic import EpisodicMemory, EpisodicMemoryConfig
from app.sandbox.e2b_sandbox import SecureSandbox, SandboxConfig

# Mock Mem0 and Qdrant to avoid actual connections during unit tests
@pytest.fixture
def mock_mem0():
    # Use patch.object to patch the actual instance method if possible, 
    # but since we are creating a new instance inside __init__, 
    # we need to patch the class `Memory.from_config` which returns the mock
    with patch("app.memory.semantic.Memory.from_config") as MockFromConfig:
        mock_instance = MagicMock()
        MockFromConfig.return_value = mock_instance
        
        mock_instance.add.return_value = {"id": "test_id"}
        mock_instance.search.return_value = [{"text": "test memory"}]
        mock_instance.get_all.return_value = [{"text": "test memory"}]
        
        yield mock_instance

def test_semantic_memory_initialization(mock_mem0):
    config = SemanticMemoryConfig(user_id="test_user", qdrant_url="http://localhost:6333")
    memory = SemanticMemory(config)
    assert memory.memory is not None
    
def test_semantic_memory_add(mock_mem0):
    config = SemanticMemoryConfig(user_id="test_user")
    memory = SemanticMemory(config)
    memory.add("The user likes Python.")
    mock_mem0.add.assert_called()

def test_episodic_memory_db_creation(tmp_path):
    db_file = tmp_path / "test_episodic.db"
    config = EpisodicMemoryConfig(db_path=str(db_file))
    memory = EpisodicMemory(config)
    
    assert db_file.exists()
    
    # Check table existence
    import sqlite3
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_summaries'")
    assert cursor.fetchone() is not None
    conn.close()

def test_episodic_memory_save_retrieve(tmp_path):
    db_file = tmp_path / "test_episodic_rw.db"
    config = EpisodicMemoryConfig(db_path=str(db_file))
    memory = EpisodicMemory(config)
    
    session_id = "sess_123"
    summary = "User discussed Python project."
    
    memory.save_summary(session_id, summary)
    retrieved = memory.get_summary(session_id)
    
    assert retrieved == summary

# Mock E2B Sandbox
@pytest.fixture
def mock_e2b_sandbox():
    with patch("app.sandbox.e2b_sandbox.Sandbox") as MockSandbox:
        mock_instance = MockSandbox.return_value
        mock_instance.run_code.return_value = MagicMock(stdout="Hello World", stderr="", error=None)
        yield mock_instance

@pytest.mark.asyncio
async def test_sandbox_execution(mock_e2b_sandbox):
    config = SandboxConfig(api_key="fake_key")
    sandbox = SecureSandbox(config)
    
    result = await sandbox.execute_code("print('Hello World')")
    
    assert result.stdout == "Hello World"
    assert result.error is None
    mock_e2b_sandbox.run_code.assert_called_with("print('Hello World')")

@pytest.mark.asyncio
async def test_sandbox_missing_key():
    config = SandboxConfig(api_key=None)
    sandbox = SecureSandbox(config)
    
    result = await sandbox.execute_code("print('Fail')")
    
    assert "API Key missing" in result.stderr
