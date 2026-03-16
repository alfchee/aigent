import pytest
import time
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

def test_episodic_memory_versioning_window(tmp_path):
    db_file = tmp_path / "test_episodic_versions.db"
    memory = EpisodicMemory(EpisodicMemoryConfig(db_path=str(db_file)))
    session_id = "sess_window"
    memory.append_summary(session_id, "summary v1")
    time.sleep(1)
    marker = int(time.time())
    time.sleep(1)
    memory.append_summary(session_id, "summary v2")
    items = memory.list_summaries(session_id=session_id, since_ts=marker)
    assert len(items) == 1
    assert items[0]["summary"] == "summary v2"

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

@pytest.mark.asyncio
async def test_sandbox_role_profile_timeout(tmp_path):
    config = SandboxConfig(base_dir=str(tmp_path))
    sandbox = SecureSandbox(config)
    result = await sandbox.execute_code("import time\ntime.sleep(10)", timeout=30, session_id="sess_role", role_id="researcher")
    assert result.error in {"Timeout", "ExitCode:-9", "ExitCode:137"}

@pytest.mark.asyncio
async def test_sandbox_role_allowlist_violation(tmp_path):
    config = SandboxConfig(base_dir=str(tmp_path))
    sandbox = SecureSandbox(config)
    result = await sandbox.execute_code("import itertools\nprint('x')", timeout=3, session_id="sess_allow", role_id="researcher")
    assert result.error == "PolicyViolation"
    assert "no permitido" in result.stderr

@pytest.mark.asyncio
async def test_sandbox_metrics_snapshot(tmp_path):
    config = SandboxConfig(base_dir=str(tmp_path))
    sandbox = SecureSandbox(config)
    await sandbox.execute_code("print('ok')", timeout=3, session_id="sess_metrics", role_id="default")
    metrics = sandbox.metrics_snapshot()
    assert "global" in metrics
    assert metrics["global"]["total_runs"] >= 1
    assert metrics["default"]["success_runs"] >= 1
