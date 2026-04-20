from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_soul():
    response = client.get("/config/soul")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "soul" in data
    assert isinstance(data["soul"], str)

def test_update_soul():
    new_soul = "You are an automated test agent."
    response = client.put("/config/soul", json={"soul": new_soul})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["soul"] == new_soul
    
    # Verify it persisted
    response2 = client.get("/config/soul")
    assert response2.json()["soul"] == new_soul
