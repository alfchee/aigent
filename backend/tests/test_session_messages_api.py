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
        ws_path = Path(self.tmp.name) / "workspace"
        os.environ["NAVIBOT_WORKSPACE_DIR"] = str(ws_path)

        import app.core.persistence as persistence

        importlib.reload(persistence)
        persistence.init_db()
        self.persistence = persistence

        import app.core.filesystem as fs
        importlib.reload(fs)
        self.fs = fs

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

    def test_sessions_crud_and_workspace_cleanup(self):
        session_id = "s_crud"

        r = self.client.post("/api/sessions", json={"id": session_id, "title": "Mi Sesión"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], session_id)

        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        sessions = r.json()["sessions"]
        self.assertTrue(any(s["id"] == session_id and s["title"] == "Mi Sesión" for s in sessions))

        r = self.client.patch(f"/api/sessions/{session_id}", json={"title": "Título Nuevo"})
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        sessions = r.json()["sessions"]
        self.assertTrue(any(s["id"] == session_id and s["title"] == "Título Nuevo" for s in sessions))

        ws = self.fs.SessionWorkspace(session_id)
        ws.write_text("hello.txt", "hola")
        # Check using safe_path because workspace structure changed (no longer at BASE/session_id)
        self.assertTrue(ws.safe_path("hello.txt").exists())

        p = self.persistence
        p.save_chat_message(session_id, "user", {"role": "user", "parts": [{"text": "hola"}]})

        # Call delete with purge=True to ensure DB records and files are removed
        r = self.client.delete(f"/api/sessions/{session_id}?purge=true")
        self.assertEqual(r.status_code, 200)

        # After purge, the workspace root should be gone
        self.assertFalse(ws.root.exists())

        with p.db_session() as db:
            left = db.query(p.ChatMessage).filter(p.ChatMessage.session_id == session_id).all()
            self.assertEqual(len(left), 0)

    def test_settings_models_and_session_model_validation(self):
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        tiers = payload["settings"]["tiers"]
        self.assertEqual(tiers["fast"], ["gemini-3-flash-preview", "gemini-flash-latest"])
        self.assertEqual(tiers["fallback"], ["gemini-3-pro-preview", "gemini-2.5-pro"])

        models = payload["settings"]["models"]
        self.assertTrue(all(m in models for m in tiers["fast"]))
        self.assertTrue(all(m in models for m in tiers["fallback"]))

        r = self.client.put("/api/settings", json={"current_model": "gemini-1.5-pro"})
        self.assertEqual(r.status_code, 400)

        r = self.client.put("/api/settings", json={"fallback_model": "gemini-2.0-flash"})
        self.assertEqual(r.status_code, 400)

        session_id = "s_settings"
        r = self.client.post("/api/sessions", json={"id": session_id, "title": "Settings"})
        self.assertEqual(r.status_code, 200)

        r = self.client.put(f"/api/sessions/{session_id}/settings", json={"model_name": "gemini-1.5-pro"})
        self.assertEqual(r.status_code, 400)

        r = self.client.put(f"/api/sessions/{session_id}/settings", json={"model_name": "gemini-2.5-pro"})
        self.assertEqual(r.status_code, 200)

        r = self.client.get(f"/api/sessions/{session_id}/settings")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["model_name"], "gemini-2.5-pro")


if __name__ == "__main__":
    unittest.main()
