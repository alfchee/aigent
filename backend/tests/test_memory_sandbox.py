import pytest
from app.memory.semantic import SemanticMemory, SemanticMemoryConfig
from app.memory.episodic import EpisodicMemory, EpisodicMemoryConfig
from app.sandbox.e2b_sandbox import SecureSandbox, SandboxConfig


def test_semantic_memory_fallback_search(monkeypatch):
    def fail_openviking(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr("app.memory.semantic.OpenVikingMemoryController", fail_openviking)
    config = SemanticMemoryConfig(user_id="test_user")
    memory = SemanticMemory(config)
    memory.add("The user likes Python.")
    memory.add("The user likes Rust.")
    results = memory.search("python")
    assert any("Python" in item for item in results)

def test_episodic_memory_db_creation(tmp_path):
    db_file = tmp_path / "test_episodic.db"
    config = EpisodicMemoryConfig(db_path=str(db_file))
    memory = EpisodicMemory(config)
    
    assert db_file.exists()
    
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

@pytest.mark.asyncio
async def test_sandbox_execution_success(tmp_path):
    config = SandboxConfig(base_dir=str(tmp_path))
    sandbox = SecureSandbox(config)

    result = await sandbox.execute_code("print('Hello World')", timeout=3, session_id="sess_ok")

    assert result.stdout.strip() == "Hello World"
    assert result.error is None
    assert result.stderr == ""

@pytest.mark.asyncio
async def test_sandbox_policy_violation(tmp_path):
    config = SandboxConfig(base_dir=str(tmp_path))
    sandbox = SecureSandbox(config)
    result = await sandbox.execute_code("import os\nprint('Fail')", timeout=3, session_id="sess_deny")
    assert result.error == "PolicyViolation"
    assert "Blocked code pattern" in result.stderr
