"""API-level tests for the /roles CRUD endpoints."""
import json
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_role(role_id: str = "test_worker", **kwargs) -> dict:
    return {
        "role_id": role_id,
        "name": "Test Worker",
        "description": "A role used in tests",
        "model": "gpt-4o",
        "system_prompt": "You are a test worker.",
        "skills": [],
        "mcp_servers": [],
        **kwargs,
    }


@pytest.fixture(autouse=True)
def clean_test_worker(client):
    """Delete the test role before and after each test to ensure isolation."""
    client.delete("/roles/test_worker")
    yield
    client.delete("/roles/test_worker")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /roles
# ---------------------------------------------------------------------------

def test_list_roles_returns_ok(client):
    response = client.get("/roles")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "workers" in data
    assert isinstance(data["workers"], list)


# ---------------------------------------------------------------------------
# POST /roles (create)
# ---------------------------------------------------------------------------

def test_create_role_returns_201(client):
    response = client.post("/roles", json=_base_role())
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ok"
    assert data["role"]["role_id"] == "test_worker"
    assert data["role"]["created_at"] is not None
    assert data["role"]["updated_at"] is not None


def test_create_role_appears_in_list(client):
    client.post("/roles", json=_base_role())
    response = client.get("/roles")
    ids = [w["role_id"] for w in response.json()["workers"]]
    assert "test_worker" in ids


def test_create_role_duplicate_returns_409(client):
    client.post("/roles", json=_base_role())
    response = client.post("/roles", json=_base_role())
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /roles/{role_id}
# ---------------------------------------------------------------------------

def test_get_role_by_id(client):
    client.post("/roles", json=_base_role())
    response = client.get("/roles/test_worker")
    assert response.status_code == 200
    assert response.json()["role"]["role_id"] == "test_worker"


def test_get_role_not_found(client):
    response = client.get("/roles/no_such_role_xyz")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /roles/{role_id} (update)
# ---------------------------------------------------------------------------

def test_update_role_returns_updated_fields(client):
    client.post("/roles", json=_base_role())
    response = client.put("/roles/test_worker", json={"name": "Renamed Worker", "model": "gpt-4-turbo"})
    assert response.status_code == 200
    role = response.json()["role"]
    assert role["name"] == "Renamed Worker"
    assert role["model"] == "gpt-4-turbo"
    assert role["description"] == "A role used in tests"  # unchanged


def test_update_role_persists_across_get(client):
    client.post("/roles", json=_base_role())
    client.put("/roles/test_worker", json={"name": "Persisted Name"})
    response = client.get("/roles/test_worker")
    assert response.json()["role"]["name"] == "Persisted Name"


def test_update_role_not_found_returns_404(client):
    response = client.put("/roles/ghost_role", json={"name": "X"})
    assert response.status_code == 404


def test_update_role_cannot_change_role_id(client):
    client.post("/roles", json=_base_role())
    client.put("/roles/test_worker", json={"role_id": "hacked", "name": "ok"})
    # Original ID still accessible, hacked ID should not exist
    assert client.get("/roles/test_worker").status_code == 200
    assert client.get("/roles/hacked").status_code == 404


# ---------------------------------------------------------------------------
# DELETE /roles/{role_id}
# ---------------------------------------------------------------------------

def test_delete_role_removes_it(client):
    client.post("/roles", json=_base_role())
    response = client.delete("/roles/test_worker")
    assert response.status_code == 200
    assert response.json()["deleted_role_id"] == "test_worker"
    assert client.get("/roles/test_worker").status_code == 404


def test_delete_role_not_found_returns_404(client):
    response = client.delete("/roles/ghost_role_xyz")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /roles/reload
# ---------------------------------------------------------------------------

def test_reload_endpoint_returns_ok(client):
    response = client.post("/roles/reload")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "workers_count" in data
