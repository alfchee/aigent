from fastapi.testclient import TestClient

from app.main import app, chat_persistence


def test_chat_messages_endpoint(monkeypatch):
    expected = [
        {
            "id": "m1",
            "session_id": "s1",
            "conversation_id": "c1",
            "role": "user",
            "text": "hola",
            "created_at": 1111,
            "meta": {"source": "test"},
        }
    ]

    def fake_list_messages(session_id, conversation_id=None, before_created_at=None, limit=50):
        assert session_id == "s1"
        assert conversation_id == "c1"
        assert before_created_at == 2000
        assert limit == 20
        return expected

    monkeypatch.setattr(chat_persistence, "list_messages", fake_list_messages)
    client = TestClient(app)
    response = client.get(
        "/chat/s1/messages",
        params={"conversationId": "c1", "beforeCreatedAt": 2000, "limit": 20},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == "m1"
