from fastapi.testclient import TestClient

from app.main import app
from app.api import sessions as sessions_api


def test_sessions_endpoint_returns_ordered_items(monkeypatch):
    fake_items = [
        {
            "session_id": "s_recent",
            "title": "Conversación reciente",
            "last_activity": 2000,
            "total_messages": 10,
            "last_message_preview": "hola",
            "last_conversation_id": "c_recent",
            "summary": None,
            "source": "db",
        },
        {
            "session_id": "s_old",
            "title": "Conversación antigua",
            "last_activity": 1000,
            "total_messages": 3,
            "last_message_preview": "adiós",
            "last_conversation_id": "c_old",
            "summary": None,
            "source": "workspace",
        },
    ]

    monkeypatch.setattr(sessions_api, "list_session_summaries", lambda: fake_items)

    client = TestClient(app)
    response = client.get("/sessions")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 2
    assert payload["items"][0]["session_id"] == "s_recent"
    assert payload["items"][1]["session_id"] == "s_old"
