import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class TestSessionMessagesApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"

        import app.core.persistence as persistence

        importlib.reload(persistence)
        persistence.init_db()
        self.persistence = persistence

        import app.main as main

        importlib.reload(main)
        self.app = main.app
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_messages_pagination_and_order(self):
        p = self.persistence
        session_id = "s1"

        for i in range(120):
            p.save_chat_message(session_id, "user", {"role": "user", "parts": [{"text": f"u{i}"}]})
            p.save_chat_message(session_id, "assistant", {"role": "model", "parts": [{"text": f"a{i}"}]})

        r1 = self.client.get(f"/api/sessions/{session_id}/messages?limit=50")
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertEqual(data1["session_id"], session_id)
        self.assertEqual(len(data1["items"]), 50)
        self.assertTrue(data1["has_more"])

        items1 = data1["items"]
        ids1 = [m["id"] for m in items1]
        self.assertEqual(ids1, sorted(ids1))

        before_id = data1["next_before_id"]
        self.assertIsNotNone(before_id)

        r2 = self.client.get(f"/api/sessions/{session_id}/messages?limit=50&before_id={before_id}")
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(len(data2["items"]), 50)

        items2 = data2["items"]
        ids2 = [m["id"] for m in items2]
        self.assertEqual(ids2, sorted(ids2))

        self.assertLess(max(ids2), min(ids1))

    def test_corrupted_content_does_not_break(self):
        p = self.persistence
        session_id = "s2"
        p.save_chat_message(session_id, "user", "{not valid json")
        p.save_chat_message(session_id, "assistant", {"role": "model", "parts": [{"text": "ok"}]})

        r = self.client.get(f"/api/sessions/{session_id}/messages?limit=50")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertIn("content", data["items"][0])

    def test_performance_large_history(self):
        p = self.persistence
        session_id = "s_perf"
        p.save_chat_message(session_id, "user", {"role": "user", "parts": [{"text": "seed"}]})
        rows = []
        now = p._utcnow()
        for i in range(2000):
            rows.append(
                p.ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=f'{{"role":"user","parts":[{{"text":"m{i}"}}]}}',
                    created_at=now,
                )
            )
        with p.db_session() as db:
            db.add_all(rows)

        t0 = time.perf_counter()
        r = self.client.get(f"/api/sessions/{session_id}/messages?limit=50")
        dt = time.perf_counter() - t0
        self.assertEqual(r.status_code, 200)
        self.assertLess(dt, 2.0)


if __name__ == "__main__":
    unittest.main()
