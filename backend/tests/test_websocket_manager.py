import pytest
from app.api.websockets import ConnectionManager


class DummyWebSocket:
    def __init__(self, fail_send: bool = False):
        self.accepted = False
        self.fail_send = fail_send
        self.text_messages = []
        self.json_messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        if self.fail_send:
            raise RuntimeError("send failure")
        self.text_messages.append(message)

    async def send_json(self, data):
        if self.fail_send:
            raise RuntimeError("send failure")
        self.json_messages.append(data)


@pytest.mark.asyncio
async def test_connection_manager_send_and_cleanup():
    manager = ConnectionManager()
    alive = DummyWebSocket()
    dead = DummyWebSocket(fail_send=True)
    await manager.connect(alive, "s1")
    await manager.connect(dead, "s1")
    assert manager.active_count("s1") == 2
    await manager.send_json({"type": "ping"}, "s1")
    assert manager.active_count("s1") == 1
    assert alive.json_messages == [{"type": "ping"}]
