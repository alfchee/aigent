import base64
import mimetypes
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
 
 
def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
 
 
BASE_WORKSPACE = Path(os.getenv("NAVIBOT_WORKSPACE_DIR", "./workspace_data"))
 
 
class SessionWorkspace:
    def __init__(self, session_id: str):
        if not session_id or any(ch in session_id for ch in ("/", "\\", "..")):
            raise ValueError("Invalid session_id")
        self.root = (BASE_WORKSPACE / session_id).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
 
    def _normalize_virtual_path(self, virtual_path: str) -> str:
        if virtual_path is None:
            return ""
        p = str(virtual_path).strip()
        if p in ("", ".", "/"):
            return ""
        return p.lstrip("/").replace("\\", "/")
 
    def _safe_path(self, virtual_path: str) -> Path:
        rel = self._normalize_virtual_path(virtual_path)
        target = (self.root / rel).resolve()
        try:
            target.relative_to(self.root)
        except Exception:
            raise ValueError(f"Acceso denegado: {virtual_path}")
        return target

    def safe_path(self, virtual_path: str) -> Path:
        return self._safe_path(virtual_path)
 
    def list_files(self, virtual_dir: str = "/") -> list[dict[str, Any]]:
        base = self._safe_path(virtual_dir)
        if not base.exists():
            return []
        if base.is_file():
            return [self._stat_file(base)]
 
        entries: list[dict[str, Any]] = []
        for p in base.rglob("*"):
            if p.is_file():
                entries.append(self._stat_file(p))
        entries.sort(key=lambda e: e["path"])
        return entries
 
    def _stat_file(self, path: Path) -> dict[str, Any]:
        st = path.stat()
        rel = str(path.relative_to(self.root)).replace("\\", "/")
        mime, _ = mimetypes.guess_type(rel)
        return {
            "path": rel,
            "size_bytes": int(st.st_size),
            "modified_at": _utc_iso(st.st_mtime),
            "mime_type": mime,
        }
 
    def read_bytes(self, virtual_path: str) -> bytes:
        target = self._safe_path(virtual_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(virtual_path)
        return target.read_bytes()
 
    def read_text(self, virtual_path: str, encoding: str = "utf-8") -> str:
        target = self._safe_path(virtual_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(virtual_path)
        return target.read_text(encoding=encoding, errors="replace")
 
    def write_bytes(self, virtual_path: str, content: bytes) -> dict[str, Any]:
        target = self._safe_path(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return self._stat_file(target)
 
    def write_text(self, virtual_path: str, content: str, encoding: str = "utf-8") -> dict[str, Any]:
        target = self._safe_path(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return self._stat_file(target)
 
    def write_base64(self, virtual_path: str, content_b64: str) -> dict[str, Any]:
        raw = base64.b64decode(content_b64.encode("utf-8"), validate=False)
        return self.write_bytes(virtual_path, raw)
