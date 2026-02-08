import importlib
import os
import tempfile
import unittest
from pathlib import Path

from app.core.runtime_context import reset_session_id, set_session_id


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"
        import app.core.persistence as persistence
        importlib.reload(persistence)
        persistence.init_db()
        self.persistence = persistence

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load_chat_history(self):
        p = self.persistence
        p.save_chat_message("s1", "user", "hola")
        p.save_chat_message("s1", "assistant", "ok")
        history = p.load_chat_history("s1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["parts"][0]["text"], "hola")
        self.assertEqual(history[1]["role"], "model")
        self.assertEqual(history[1]["parts"][0]["text"], "ok")

    def test_tool_call_is_saved(self):
        p = self.persistence

        def add(a, b):
            return a + b

        wrapped = p.wrap_tool(add)
        token = set_session_id("s1")
        try:
            out = wrapped(2, 3)
        finally:
            reset_session_id(token)

        self.assertEqual(out, 5)
        with p.db_session() as db:
            rows = db.query(p.ToolCall).filter(p.ToolCall.session_id == "s1").all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].tool_name, "add")

    def test_save_structured_content(self):
        p = self.persistence
        # Save structured user message
        p.save_chat_message("s2", "user", {"role": "user", "parts": [{"text": "hello"}]})
        # Save structured model message
        p.save_chat_message("s2", "model", {"role": "model", "parts": [{"text": "hi"}]})
        
        history = p.load_chat_history("s2")
        self.assertEqual(len(history), 2)
        
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["parts"][0]["text"], "hello")
        
        self.assertEqual(history[1]["role"], "model")
        self.assertEqual(history[1]["parts"][0]["text"], "hi")



class TestAgentRecovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"
        import app.core.persistence as persistence
        importlib.reload(persistence)
        persistence.init_db()
        persistence.save_chat_message("s1", "user", "hola")
        persistence.save_chat_message("s1", "assistant", "ok")
        self.persistence = persistence

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_start_chat_restores_history(self):
        from app.core.agent import NaviBot

        bot = NaviBot()

        class DummyChats:
            def __init__(self):
                self.last_kwargs = None

            def create(self, **kwargs):
                self.last_kwargs = kwargs
                return object()

        class DummyAio:
            def __init__(self):
                self.chats = DummyChats()

        class DummyClient:
            def __init__(self):
                self.aio = DummyAio()

        bot.client = DummyClient()

        token = set_session_id("s1")
        try:
            await bot.start_chat(session_id="s1")
        finally:
            reset_session_id(token)

        history = bot.client.aio.chats.last_kwargs["history"]
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["parts"][0]["text"], "hola")
        self.assertEqual(history[1]["role"], "model")
        self.assertEqual(history[1]["parts"][0]["text"], "ok")