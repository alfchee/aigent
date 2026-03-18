from fastapi.testclient import TestClient
from app.main import app
from app.channels.telegram import telegram_bot


def test_telegram_webhook_secret_validation(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-123")
    client = TestClient(app)
    response = client.post("/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 403


def test_telegram_webhook_processes_update(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-123")

    async def fake_process(_payload):
        return True

    monkeypatch.setattr(telegram_bot, "process_webhook_update", fake_process)
    client = TestClient(app)
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 2},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
    )
    assert response.status_code == 200
    assert response.json()["processed"] is True
