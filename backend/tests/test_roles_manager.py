import json
import pytest
from app.core.roles import AgentRole, RoleManager


def _make_config(tmp_path, workers=None):
    """Write a minimal roles.json and return a RoleManager pointing at it."""
    config_file = tmp_path / "roles.json"
    payload = {
        "supervisor": {
            "name": "Supervisor",
            "description": "routes work",
            "model": "gemini-2.0-flash",
            "system_prompt": "route",
        },
        "workers": workers or [],
    }
    config_file.write_text(json.dumps(payload))
    return RoleManager(config_path=str(config_file)), config_file


def test_role_manager_load_and_lookup(tmp_path):
    config_file = tmp_path / "roles.json"
    payload = {
        "supervisor": {
            "name": "Supervisor",
            "description": "routes work",
            "model": "gemini-2.0-flash",
            "system_prompt": "route",
        },
        "workers": [
            {
                "role_id": "coder",
                "name": "Coder",
                "description": "writes code",
                "model": "gemini-2.0-flash",
                "system_prompt": "code",
                "skills": ["python_repl", "file_read"],
            }
        ],
    }
    config_file.write_text(json.dumps(payload))
    manager = RoleManager(config_path=str(config_file))
    assert manager.get_worker("coder") is not None
    worker = manager.role_for_skill("python_repl")
    assert worker is not None
    assert worker.role_id == "coder"


def test_role_manager_reload(tmp_path):
    config_file = tmp_path / "roles_reload.json"
    payload = {
        "supervisor": {
            "name": "Supervisor",
            "description": "routes work",
            "model": "gemini-2.0-flash",
            "system_prompt": "route",
        },
        "workers": [],
    }
    config_file.write_text(json.dumps(payload))
    manager = RoleManager(config_path=str(config_file))
    assert len(manager.get_all_workers()) == 0
    payload["workers"].append(
        {
            "role_id": "researcher",
            "name": "Researcher",
            "description": "finds info",
            "model": "gemini-2.0-flash",
            "system_prompt": "research",
            "skills": ["web_search"],
        }
    )
    config_file.write_text(json.dumps(payload))
    snapshot = manager.reload()
    assert len(snapshot.workers) == 1
    assert snapshot.workers[0].role_id == "researcher"


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

def _new_role(**kwargs) -> AgentRole:
    defaults = dict(
        role_id="analyst",
        name="Analyst",
        description="data analysis",
        model="gpt-4o",
        system_prompt="Analyze data.",
    )
    defaults.update(kwargs)
    return AgentRole(**defaults)


def test_get_role_found(tmp_path):
    manager, _ = _make_config(tmp_path, workers=[
        {"role_id": "coder", "name": "Coder", "description": "code", "model": "gpt-4o", "system_prompt": "code"}
    ])
    role = manager.get_role("coder")
    assert role.role_id == "coder"


def test_get_role_not_found(tmp_path):
    manager, _ = _make_config(tmp_path)
    with pytest.raises(KeyError, match="missing"):
        manager.get_role("missing")


def test_create_role_persists(tmp_path):
    manager, config_file = _make_config(tmp_path)
    role = _new_role(skills=["web_search"], mcp_servers=["brave"])
    created = manager.create_role(role)

    assert created.role_id == "analyst"
    assert created.created_at is not None
    assert created.updated_at is not None
    assert "web_search" in created.skills
    assert "brave" in created.mcp_servers

    # Persisted to disk
    data = json.loads(config_file.read_text())
    ids = [w["role_id"] for w in data["workers"]]
    assert "analyst" in ids

    # Visible via get_role
    fetched = manager.get_role("analyst")
    assert fetched.name == "Analyst"


def test_create_role_duplicate_raises(tmp_path):
    manager, _ = _make_config(tmp_path)
    manager.create_role(_new_role())
    with pytest.raises(ValueError, match="already exists"):
        manager.create_role(_new_role())


def test_update_role_merges_fields(tmp_path):
    manager, config_file = _make_config(tmp_path)
    manager.create_role(_new_role())

    updated = manager.update_role("analyst", {"name": "Senior Analyst", "model": "gpt-4-turbo"})

    assert updated.name == "Senior Analyst"
    assert updated.model == "gpt-4-turbo"
    assert updated.description == "data analysis"  # unchanged
    assert updated.updated_at is not None

    # Persisted
    data = json.loads(config_file.read_text())
    worker = next(w for w in data["workers"] if w["role_id"] == "analyst")
    assert worker["name"] == "Senior Analyst"


def test_update_role_cannot_change_role_id(tmp_path):
    manager, _ = _make_config(tmp_path)
    manager.create_role(_new_role())
    updated = manager.update_role("analyst", {"role_id": "hacker", "name": "Renamed"})
    # role_id must stay unchanged
    assert updated.role_id == "analyst"
    assert manager.get_role("analyst") is not None


def test_update_role_not_found(tmp_path):
    manager, _ = _make_config(tmp_path)
    with pytest.raises(KeyError, match="ghost"):
        manager.update_role("ghost", {"name": "X"})


def test_delete_role_removes_from_memory_and_disk(tmp_path):
    manager, config_file = _make_config(tmp_path)
    manager.create_role(_new_role())
    assert manager.get_worker("analyst") is not None

    manager.delete_role("analyst")

    assert manager.get_worker("analyst") is None
    data = json.loads(config_file.read_text())
    assert all(w["role_id"] != "analyst" for w in data["workers"])


def test_delete_role_not_found(tmp_path):
    manager, _ = _make_config(tmp_path)
    with pytest.raises(KeyError, match="ghost"):
        manager.delete_role("ghost")


def test_new_fields_round_trip(tmp_path):
    """AgentRole new fields survive a serialize → reload cycle."""
    manager, config_file = _make_config(tmp_path)
    role = AgentRole(
        role_id="x",
        name="X",
        description="desc",
        model="gpt-4o",
        system_prompt="sys",
        provider_override="openai",
        mcp_servers=["server_a"],
        enabled=False,
    )
    manager.create_role(role)

    # Re-load from file
    manager2 = RoleManager(config_path=str(config_file))
    fetched = manager2.get_role("x")
    assert fetched.provider_override == "openai"
    assert "server_a" in fetched.mcp_servers
    assert fetched.enabled is False
