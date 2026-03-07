import asyncio
import os
import unittest

from google.genai import types

from app.core.agent import NaviBot
from app.core.db import SessionLocal, engine, Base
from app.core.models import ChatSession, ChatMessage
from app.core.react_engine import ReActLoop


class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session_id = f"test_session_{os.getpid()}"
        db = SessionLocal()
        db.query(ChatMessage).filter(ChatMessage.session_id == self.session_id).delete()
        db.query(ChatSession).filter(ChatSession.id == self.session_id).delete()
        db.commit()
        db.close()
        self.bot = NaviBot()

    def test_save_and_load_history(self):
        history = [
            types.Content(role="user", parts=[types.Part(text="Hola")]),
            types.Content(role="model", parts=[types.Part(text="Hola, ¿en qué te ayudo?")]),
            types.Content(role="user", parts=[types.Part(text="Mi nombre es Luis")]),
            types.Content(role="model", parts=[types.Part(text="Entendido")])
        ]
        self.bot._save_history_to_db(self.session_id, history)
        loaded = self.bot._get_history_from_db(self.session_id)
        self.assertEqual(len(loaded), len(history))
        db = SessionLocal()
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


class TestReActLoopSessionId(unittest.TestCase):
    def test_react_loop_uses_session_id(self):
        agent = FakeAgent()
        loop = ReActLoop(agent=agent, session_id="session_123", max_iterations=1)
        asyncio.run(loop.execute("Prueba"))
        self.assertEqual(agent.start_calls[-1], "session_123")
        self.assertEqual(agent.send_calls[-1], "session_123")
