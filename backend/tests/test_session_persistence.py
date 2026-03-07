import asyncio
import os
import unittest

from google.genai import types

from app.core.agent import NaviBot
from app.core.persistence import SessionRecord as ChatSession, ChatMessage, Base, get_engine, save_chat_message, load_chat_history
from app.core import persistence
from app.core.react_engine import ReActLoop
from app.core.runtime_context import set_session_id
from sqlalchemy.orm import sessionmaker


class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        os.environ["NAVIBOT_DB_URL"] = "sqlite:///:memory:"
        # Reset singleton engine to force recreation with new URL
        persistence._engine = None
        persistence._session_local = None
        
        self.engine = get_engine()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session_id = f"test_session_{os.getpid()}"
        # No need to delete from in-memory DB, it's empty
        self.bot = NaviBot()

    def test_save_and_load_history(self):
        history = [
            types.Content(role="user", parts=[types.Part(text="Hola")]),
            types.Content(role="model", parts=[types.Part(text="Hola, ¿en qué te ayudo?")]),
            types.Content(role="user", parts=[types.Part(text="Mi nombre es Luis")]),
            types.Content(role="model", parts=[types.Part(text="Entendido")])
        ]
        
        # Save history using persistence function
        for item in history:
            save_chat_message(self.session_id, item.role, item)

        loaded = load_chat_history(self.session_id)
        self.assertEqual(len(loaded), len(history))
        db = self.SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.id == self.session_id).first()
        count = db.query(ChatMessage).filter(ChatMessage.session_id == self.session_id).count()
        db.close()
        self.assertIsNotNone(session)
        self.assertEqual(count, len(history))


class MockChatSession:
    def get_history(self):
        return []


class FakeAgent:
    def __init__(self):
        self.start_calls = []
        self.send_calls = []
        self._chat_session = MockChatSession()

    async def start_chat(self, session_id: str = "default", history=None):
        self.start_calls.append(session_id)

    async def send_message(self, message: str, session_id: str = "default"):
        self.send_calls.append(session_id)

        class Response:
            text = "ok"

        return Response()

    async def ensure_session(self, session_id: str):
        self.start_calls.append(session_id)


class TestReActLoopSessionId(unittest.TestCase):
    def test_react_loop_uses_session_id(self):
        # We need to set the session_id in the runtime context because ReActLoop uses it via get_session_id()
        session_id = "session_123"
        set_session_id(session_id)
        
        agent = FakeAgent()
        loop = ReActLoop(agent=agent, session_id=session_id, max_iterations=1)
        asyncio.run(loop.execute("Prueba"))
        self.assertEqual(agent.start_calls[-1], session_id)
        self.assertEqual(agent.send_calls[-1], "session_123")
