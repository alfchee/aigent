import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class DummyBot:
    async def ensure_session(self, session_id: str):
        return None

    def get_history(self, session_id: str):
        return []

    async def send_message(self, message: str):
        raise RuntimeError("forced_failure")


class TestChatFailureRepro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"
        import app.core.persistence as persistence

        importlib.reload(persistence)
        persistence.init_db()

        import app.main as main

        importlib.reload(main)
        class DummyPool:
            def get(self, model_name: str):
                return DummyBot()

        main.bot_pool = DummyPool()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_chat_failure_returns_error_id(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "hola", "session_id": "s1", "use_react_loop": False},
        )
        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertIn("Internal Server Error", payload.get("detail", ""))
