import json
from app.core.roles import RoleManager


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
