import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.persistence as persistence
import app.core.filesystem as filesystem
import app.core.code_execution_service as code_execution_service
import app.api.code_execution as code_execution_pkg
import app.api.files as files_pkg


def _has_module(name: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


class TestCodeExecutionApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        
        # Configure environment for this test
        db_path = Path(self.tmp.name) / "test.db"
        os.environ["NAVIBOT_DB_URL"] = f"sqlite:///{db_path}"
        os.environ["NAVIBOT_WORKSPACE_DIR"] = self.tmp.name

        # Reload modules to pick up new configuration
        importlib.reload(persistence)
        persistence.init_db()
        
        importlib.reload(filesystem)
        importlib.reload(code_execution_service)
        importlib.reload(code_execution_pkg)
        importlib.reload(files_pkg)

        # Create app with reloaded routers
        app = FastAPI()
        app.include_router(code_execution_pkg.router)
        app.include_router(files_pkg.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_execute_simple_math(self):
        r = self.client.post(
            "/api/execute-code",
            json={"session_id": "s1", "code": "print(sum(range(10)))\n", "timeout_seconds": 5},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("45", data["stdout"])

    def test_execute_timeout(self):
        r = self.client.post(
            "/api/execute-code",
            json={"session_id": "s1", "code": "import time\ntime.sleep(2)\n", "timeout_seconds": 1},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "timeout")

    def test_execute_blocks_os_import(self):
        r = self.client.post(
            "/api/execute-code",
            json={"session_id": "s1", "code": "import os\nprint('x')\n", "timeout_seconds": 5},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn(data["status"], {"blocked", "syntax_error"})
        self.assertIn("Imports no permitidos", data.get("stderr", ""))

    def test_execute_blocks_import_dunder(self):
        r = self.client.post(
            "/api/execute-code",
            json={"session_id": "s1", "code": "__import__('os').system('echo hi')\n", "timeout_seconds": 5},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "blocked")
        self.assertIn("Llamada no permitida", data.get("stderr", ""))

    def test_execute_creates_png_with_pillow(self):
        if not _has_module("PIL"):
            self.skipTest("pillow no instalado")

        code = "\n".join(
            [
                "from PIL import Image",
                "img = Image.new('RGB', (16, 16), (255, 0, 0))",
                "img.save('out.png')",
                "print('ok')",
                "",
            ]
        )
        r = self.client.post("/api/execute-code", json={"session_id": "s1", "code": code, "timeout_seconds": 10})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        paths = [f["path"] for f in data.get("created_files") or []]
        pngs = [p for p in paths if p.endswith(".png")]
        self.assertTrue(pngs)

        p = pngs[0]
        rf = self.client.get(f"/api/files/s1/{p}")
        self.assertEqual(rf.status_code, 200)
        self.assertEqual(rf.content[:8], b"\x89PNG\r\n\x1a\n")

    def test_execute_csv_analysis_stdlib(self):
        ws = filesystem.SessionWorkspace("s1")
        ws.write_text("uploads/data.csv", "a,b\n1,2\n3,4\n")
        code = "\n".join(
            [
                "import csv",
                "with open('session/uploads/data.csv', 'r', encoding='utf-8') as f:",
                "    rows = list(csv.DictReader(f))",
                "s = sum(int(r['a']) for r in rows)",
                "print(s)",
                "",
            ]
        )
        r = self.client.post("/api/execute-code", json={"session_id": "s1", "code": code, "timeout_seconds": 10})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("4", data["stdout"])

    def test_execute_matplotlib_plot(self):
        if not _has_module("matplotlib"):
            self.skipTest("matplotlib no instalado")

        code = "\n".join(
            [
                "import matplotlib.pyplot as plt",
                "plt.plot([1,2,3],[1,4,9])",
                "plt.title('t')",
                "plt.savefig('plot.png')",
                "print('done')",
                "",
            ]
        )
        r = self.client.post("/api/execute-code", json={"session_id": "s1", "code": code, "timeout_seconds": 20})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        paths = [f["path"] for f in data.get("created_files") or []]
        self.assertTrue(any(p.endswith("plot.png") for p in paths))

    def test_list_and_cleanup(self):
        r = self.client.post(
            "/api/execute-code",
            json={"session_id": "s1", "code": "print('hello')\n", "timeout_seconds": 5},
        )
        self.assertEqual(r.status_code, 200)
        run_id = r.json().get("run_id")
        self.assertTrue(run_id)

        r = self.client.get("/api/code-results/s1")
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        self.assertTrue(any(i.get("run_id") == run_id for i in items))

        r = self.client.delete("/api/code-cleanup/s1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("removed_runs", r.json())
