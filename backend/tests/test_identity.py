import os
import pytest
from pathlib import Path
from app.core.identity import IdentityManager, DEFAULT_SOUL

def test_identity_manager_initialization(tmp_path, monkeypatch):
    # Mock workspace_config_dir to use tmp_path
    monkeypatch.setattr("app.core.identity.workspace_config_dir", lambda: tmp_path)
    
    manager = IdentityManager()
    
    # Should create default soul file
    soul_file = tmp_path / "soul_prompt.txt"
    assert soul_file.exists()
    # update_soul strips whitespace, so compare against the stripped default
    assert manager.get_soul() == DEFAULT_SOUL.strip()

def test_identity_manager_update(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.identity.workspace_config_dir", lambda: tmp_path)
    
    manager = IdentityManager()
    new_soul = "You are a specialized test agent."
    manager.update_soul(new_soul)
    
    assert manager.get_soul() == new_soul
    soul_file = tmp_path / "soul_prompt.txt"
    assert soul_file.read_text(encoding="utf-8") == new_soul
