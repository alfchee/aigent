import asyncio
import json
import tempfile
import unittest
from pathlib import Path
 
from fastapi import FastAPI
from fastapi.testclient import TestClient
 
import app.core.filesystem as filesystem
from app.api.files import router as files_router
from app.core.runtime_context import reset_event_callback, reset_session_id, set_event_callback, set_session_id
from app.skills import system as system_tools
 
 
class TestSessionWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        filesystem.BASE_WORKSPACE = Path(self.tmp.name)
 
    def tearDown(self):
        self.tmp.cleanup()
 
    def test_path_traversal_blocked(self):
        ws = filesystem.SessionWorkspace("s1")
        ws.write_text("a.txt", "ok")
        with self.assertRaises(ValueError):
            ws.write_text("../evil.txt", "nope")
 
    def test_list_files_metadata(self):
        ws = filesystem.SessionWorkspace("s1")
        ws.write_text("dir/hello.txt", "hola")
        files = ws.list_files("/")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["path"], "dir/hello.txt")
        self.assertIn("size_bytes", files[0])
        self.assertIn("modified_at", files[0])
 
 
class TestFileApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        filesystem.BASE_WORKSPACE = Path(self.tmp.name)
        app = FastAPI()
        app.include_router(files_router)
        self.client = TestClient(app)
 
    def tearDown(self):
        self.tmp.cleanup()
 
    def test_upload_and_list_and_get(self):
        session_id = "s1"
        r = self.client.post(
            "/api/upload",
            data={"session_id": session_id},
            files={"file": ("test.txt", b"hola", "text/plain")},
        )
        self.assertEqual(r.status_code, 200)
        saved_path = r.json()["saved"]["path"]
 
        r = self.client.get(f"/api/files/{session_id}")
        self.assertEqual(r.status_code, 200)
        paths = [f["path"] for f in r.json()["files"]]
        self.assertIn(saved_path, paths)
 
        r = self.client.get(f"/api/files/{session_id}/{saved_path}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"hola")
 
 
class TestToolEvents(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        filesystem.BASE_WORKSPACE = Path(self.tmp.name)
        self.session_token = set_session_id("s1")
        self.events = []
 
        async def cb(event_type: str, data: dict):
            self.events.append((event_type, data))
 
        self.cb_token = set_event_callback(cb)
 
    async def asyncTearDown(self):
        reset_session_id(self.session_token)
        reset_event_callback(self.cb_token)
        self.tmp.cleanup()
 
    async def test_create_file_emits_artifact(self):
        out = system_tools.create_file("/hello.txt", "hola")
        payload = json.loads(out)
        self.assertEqual(payload["saved"]["path"], "hello.txt")
        await asyncio.sleep(0)
        self.assertTrue(any(t == "artifact" and e.get("op") == "write" for t, e in self.events))
