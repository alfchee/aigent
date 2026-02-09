import importlib
import os
import tempfile
import types as pytypes
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.runtime_context import reset_session_id, set_session_id


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


class TestAgentGrounding(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"
        ws_path = Path(self.tmp.name) / "workspace"
        os.environ["NAVIBOT_WORKSPACE_DIR"] = str(ws_path)
        import app.core.persistence as persistence

        importlib.reload(persistence)
        persistence.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_grounding_not_appended_with_tools(self):
        with patch.dict(os.environ, {"ENABLE_GOOGLE_GROUNDING": "true", "GOOGLE_GROUNDING_MODE": "auto"}):
            import app.core.agent as agent

            importlib.reload(agent)
            bot = agent.NaviBot()
            bot.client = DummyClient()

            def fake_config(**kwargs):
                return pytypes.SimpleNamespace(**kwargs)

            with patch("app.core.agent.types.GenerateContentConfig", side_effect=fake_config):
                token = set_session_id("s1")
                try:
                    await bot.start_chat(session_id="s1")
                finally:
                    reset_session_id(token)

            tools_payload = bot.client.aio.chats.last_kwargs["config"].tools
            self.assertTrue(tools_payload)
            self.assertNotIn({"google_search_retrieval": {}}, tools_payload)

    async def test_grounding_only_mode(self):
        with patch.dict(os.environ, {"ENABLE_GOOGLE_GROUNDING": "true", "GOOGLE_GROUNDING_MODE": "only"}):
            import app.core.agent as agent

            importlib.reload(agent)
            bot = agent.NaviBot()
            bot.client = DummyClient()

            def fake_config(**kwargs):
                return pytypes.SimpleNamespace(**kwargs)

            with patch("app.core.agent.types.GenerateContentConfig", side_effect=fake_config):
                token = set_session_id("s2")
                try:
                    await bot.start_chat(session_id="s2")
                finally:
                    reset_session_id(token)

            tools_payload = bot.client.aio.chats.last_kwargs["config"].tools
            self.assertEqual(tools_payload, [{"google_search_retrieval": {}}])
