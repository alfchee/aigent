import base64
import json
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from fnmatch import fnmatch
from uuid import uuid4

from app.core.persistence import SessionRecord, db_session
 
 
def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _safe_json_loads(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _format_session_timestamp(dt: datetime) -> str:
    safe = dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    safe = safe.replace("+00:00", "Z")
    safe = safe.replace(":", "-")
    return safe
 
 
BASE_WORKSPACE = Path(os.getenv("NAVIBOT_WORKSPACE_DIR", "./workspace_data")).resolve()
SESSIONS_ROOT = BASE_WORKSPACE / "sessions"
TRASH_DIR_NAME = ".trash"
TRASH_ITEMS_DIR = "items"
TRASH_AUDIT_FILENAME = "audit.jsonl"


def _workspace_relative_root(session_id: str, status: str, timestamp: str) -> str:
    return f"sessions/{session_id}/{status}/{timestamp}"


def _ensure_workspace_meta(session_id: str) -> dict[str, Any]:
    with db_session() as db:
        rec = db.get(SessionRecord, session_id)
        if rec is None:
            rec = SessionRecord(id=session_id)
            db.add(rec)
            db.flush()

        meta = _safe_json_loads(rec.meta_json)
        workspace = meta.get("workspace") if isinstance(meta.get("workspace"), dict) else {}
        status = workspace.get("status") if isinstance(workspace.get("status"), str) else "active"
        timestamp = workspace.get("timestamp")

        if not timestamp:
            created_at = rec.created_at or datetime.now(tz=timezone.utc)
            timestamp = _format_session_timestamp(created_at)
            workspace = {
                "status": status,
                "timestamp": timestamp,
                "relative_root": _workspace_relative_root(session_id, status, timestamp),
                "archived_at": workspace.get("archived_at"),
            }
            meta["workspace"] = workspace
            rec.meta_json = json.dumps(meta, ensure_ascii=False)
            rec.updated_at = datetime.now(tz=timezone.utc)
        else:
            if "relative_root" not in workspace:
                workspace["relative_root"] = _workspace_relative_root(session_id, status, timestamp)
                meta["workspace"] = workspace
                rec.meta_json = json.dumps(meta, ensure_ascii=False)
                rec.updated_at = datetime.now(tz=timezone.utc)
        return workspace


def get_workspace_info(session_id: str) -> dict[str, Any]:
    workspace = _ensure_workspace_meta(session_id)
    status = workspace.get("status", "active")
    timestamp = workspace.get("timestamp")
    rel_root = workspace.get("relative_root") or _workspace_relative_root(session_id, status, timestamp)
    abs_root = (BASE_WORKSPACE / rel_root).resolve()
    legacy_root = (BASE_WORKSPACE / session_id).resolve()
    if status == "active" and not abs_root.exists() and legacy_root.exists() and legacy_root.is_dir():
        abs_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_root), str(abs_root))
    return {
        "session_id": session_id,
        "status": status,
        "timestamp": timestamp,
        "relative_root": rel_root,
        "root": str(abs_root),
        "archived_at": workspace.get("archived_at"),
    }


def _set_workspace_status(session_id: str, status: str, archived_at: Optional[str] = None) -> dict[str, Any]:
    with db_session() as db:
        rec = db.get(SessionRecord, session_id)
        if rec is None:
            rec = SessionRecord(id=session_id)
            db.add(rec)
            db.flush()
        meta = _safe_json_loads(rec.meta_json)
        workspace = meta.get("workspace") if isinstance(meta.get("workspace"), dict) else {}
        timestamp = workspace.get("timestamp") or _format_session_timestamp(rec.created_at or datetime.now(tz=timezone.utc))
        workspace.update(
            {
                "status": status,
                "timestamp": timestamp,
                "relative_root": _workspace_relative_root(session_id, status, timestamp),
                "archived_at": archived_at,
            }
        )
        meta["workspace"] = workspace
        rec.meta_json = json.dumps(meta, ensure_ascii=False)
        rec.updated_at = datetime.now(tz=timezone.utc)
    return workspace


def archive_session_workspace(session_id: str) -> dict[str, Any]:
    info = get_workspace_info(session_id)
    if info["status"] == "archived":
        return info
    active_root = Path(info["root"])
    workspace = _set_workspace_status(session_id, "archived", archived_at=datetime.now(tz=timezone.utc).isoformat())
    archive_root = (BASE_WORKSPACE / workspace["relative_root"]).resolve()
    archive_root.parent.mkdir(parents=True, exist_ok=True)
    if active_root.exists():
        shutil.move(str(active_root), str(archive_root))
    return get_workspace_info(session_id)


def restore_session_workspace(session_id: str) -> dict[str, Any]:
    info = get_workspace_info(session_id)
    if info["status"] != "archived":
        return info
    archived_root = Path(info["root"])
    workspace = _set_workspace_status(session_id, "active", archived_at=None)
    active_root = (BASE_WORKSPACE / workspace["relative_root"]).resolve()
    active_root.parent.mkdir(parents=True, exist_ok=True)
    if archived_root.exists():
        shutil.move(str(archived_root), str(active_root))
    return get_workspace_info(session_id)


def cleanup_archived_workspaces(retention_days: int = 30) -> dict[str, Any]:
    retention_days = max(1, min(int(retention_days or 30), 365))
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (retention_days * 86400)
    removed = 0
    with db_session() as db:
        sessions = db.query(SessionRecord).all()
        for rec in sessions:
            meta = _safe_json_loads(rec.meta_json)
            workspace = meta.get("workspace") if isinstance(meta.get("workspace"), dict) else {}
            if workspace.get("status") != "archived":
                continue
            archived_at = workspace.get("archived_at")
            try:
                archived_ts = datetime.fromisoformat(archived_at).timestamp() if archived_at else 0
            except Exception:
                archived_ts = 0
            if archived_ts and archived_ts < cutoff:
                rel_root = workspace.get("relative_root")
                if rel_root:
                    abs_root = (BASE_WORKSPACE / rel_root).resolve()
                    if abs_root.exists():
                        shutil.rmtree(abs_root, ignore_errors=True)
                        removed += 1
                workspace["status"] = "purged"
                meta["workspace"] = workspace
                rec.meta_json = json.dumps(meta, ensure_ascii=False)
                rec.updated_at = datetime.now(tz=timezone.utc)
    return {"removed": removed, "retention_days": retention_days}


def auto_archive_inactive_sessions(max_idle_days: int = 7) -> dict[str, Any]:
    max_idle_days = max(1, min(int(max_idle_days or 7), 365))
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_idle_days)
    candidates: list[str] = []
    with db_session() as db:
        sessions = db.query(SessionRecord).all()
        for rec in sessions:
            if rec.updated_at and rec.updated_at >= cutoff:
                continue
            meta = _safe_json_loads(rec.meta_json)
            workspace = meta.get("workspace") if isinstance(meta.get("workspace"), dict) else {}
            status = workspace.get("status")
            if status in {"archived", "purged"}:
                continue
            if rec.id:
                candidates.append(rec.id)
    moved = 0
    for sid in candidates:
        try:
            info = get_workspace_info(sid)
            if info["status"] != "archived":
                archive_session_workspace(sid)
                moved += 1
        except Exception:
            continue
    return {"archived": moved, "max_idle_days": max_idle_days}
 
 
class SessionWorkspace:
    def __init__(self, session_id: str, allow_archived: bool = False):
        if not session_id or any(ch in session_id for ch in ("/", "\\", "..")):
            raise ValueError("Invalid session_id")
        info = get_workspace_info(session_id)
        status = info.get("status")
        if status in {"archived", "purged"} and not allow_archived:
            raise ValueError("Sesión archivada")
        self.session_id = session_id
        self.info = info
        self.root = Path(info["root"]).resolve()
        if status == "active":
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
                rel_parts = p.relative_to(self.root).parts
                if TRASH_DIR_NAME in rel_parts:
                    continue
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
        meta = self._stat_file(target)
        self._record_file(meta.get("path"))
        return meta
 
    def write_text(self, virtual_path: str, content: str, encoding: str = "utf-8") -> dict[str, Any]:
        target = self._safe_path(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        meta = self._stat_file(target)
        self._record_file(meta.get("path"))
        return meta
 
    def write_base64(self, virtual_path: str, content_b64: str) -> dict[str, Any]:
        raw = base64.b64decode(content_b64.encode("utf-8"), validate=False)
        return self.write_bytes(virtual_path, raw)

    def _record_file(self, rel_path: Optional[str]) -> None:
        if not rel_path:
            return
        with db_session() as db:
            rec = db.get(SessionRecord, self.session_id)
            if rec is None:
                rec = SessionRecord(id=self.session_id)
                db.add(rec)
                db.flush()
            meta = _safe_json_loads(rec.meta_json)
            files = meta.get("files")
            file_map = {}
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, dict):
                        path = item.get("path")
                        if isinstance(path, str) and path:
                            file_map[path] = item
            now_iso = datetime.now(tz=timezone.utc).isoformat()
            file_map[rel_path] = {"path": rel_path, "updated_at": now_iso}
            meta["files"] = list(file_map.values())
            rec.meta_json = json.dumps(meta, ensure_ascii=False)
            rec.updated_at = datetime.now(tz=timezone.utc)


def _trash_root(ws: SessionWorkspace) -> Path:
    return ws._safe_path(TRASH_DIR_NAME)


def _ensure_trash_root(ws: SessionWorkspace) -> Path:
    root = _trash_root(ws)
    (root / TRASH_ITEMS_DIR).mkdir(parents=True, exist_ok=True)
    return root


def _audit_path(ws: SessionWorkspace) -> Path:
    return _ensure_trash_root(ws) / TRASH_AUDIT_FILENAME


def _append_audit(ws: SessionWorkspace, entry: dict[str, Any]) -> None:
    entry = {**entry, "timestamp": datetime.now(tz=timezone.utc).isoformat()}
    path = _audit_path(ws)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _is_protected_path(rel: str) -> bool:
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return True
    if parts[0] == TRASH_DIR_NAME:
        return True
    protected_names = {".env", ".git", ".gitignore", "workspace.json", "session.json", "settings.json"}
    if any(p in protected_names for p in parts):
        return True
    lowered = "/".join(parts).lower()
    if "secret" in lowered or "credential" in lowered:
        return True
    return False


def delete_artifact(
    session_id: str,
    path: str,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
    allow_archived: bool = False,
) -> dict[str, Any]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    rel = ws._normalize_virtual_path(path)
    if not rel:
        raise ValueError("Ruta inválida")
    if _is_protected_path(rel):
        raise ValueError("Elemento protegido")
    target = ws._safe_path(rel)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(rel)
    size = int(target.stat().st_size)
    _ensure_trash_root(ws)
    trash_id = f"{int(datetime.now(tz=timezone.utc).timestamp())}_{uuid4().hex[:8]}"
    item_dir = _trash_root(ws) / TRASH_ITEMS_DIR / trash_id
    item_dir.mkdir(parents=True, exist_ok=True)
    dest = item_dir / "file"
    shutil.move(str(target), str(dest))
    now = datetime.now(tz=timezone.utc)
    retention_days = max(1, min(int(os.getenv("NAVIBOT_TRASH_RETENTION_DAYS", "7")), 365))
    restore_until = now + timedelta(days=retention_days)
    meta = {
        "trash_id": trash_id,
        "path": rel,
        "deleted_at": now.isoformat(),
        "restore_until": restore_until.isoformat(),
        "size_bytes": size,
        "actor": actor,
        "reason": reason,
        "retention_days": retention_days,
    }
    (item_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _append_audit(
        ws,
        {
            "op": "delete",
            "path": rel,
            "trash_id": trash_id,
            "size_bytes": size,
            "actor": actor,
            "reason": reason,
            "restore_until": restore_until.isoformat(),
        },
    )
    return {**meta, "freed_bytes": size}


def list_trash(session_id: str, allow_archived: bool = False) -> list[dict[str, Any]]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    root = _trash_root(ws)
    items_dir = root / TRASH_ITEMS_DIR
    if not items_dir.exists():
        return []
    now = datetime.now(tz=timezone.utc)
    results: list[dict[str, Any]] = []
    for item in items_dir.iterdir():
        if not item.is_dir():
            continue
        meta_path = item / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                continue
        except Exception:
            continue
        restore_until = meta.get("restore_until")
        expired = False
        if isinstance(restore_until, str):
            try:
                expired = datetime.fromisoformat(restore_until) < now
            except Exception:
                expired = False
        results.append({**meta, "expired": expired})
    results.sort(key=lambda r: r.get("deleted_at") or "", reverse=True)
    return results


def restore_artifact(
    session_id: str,
    trash_id: str,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
    allow_archived: bool = False,
) -> dict[str, Any]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    item_dir = _trash_root(ws) / TRASH_ITEMS_DIR / trash_id
    meta_path = item_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(trash_id)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("Metadata inválida")
    restore_until = meta.get("restore_until")
    if isinstance(restore_until, str):
        try:
            if datetime.fromisoformat(restore_until) < datetime.now(tz=timezone.utc):
                raise ValueError("Periodo de restauración vencido")
        except ValueError:
            raise
        except Exception:
            pass
    rel = str(meta.get("path") or "")
    if _is_protected_path(rel):
        raise ValueError("Elemento protegido")
    target = ws._safe_path(rel)
    if target.exists():
        raise ValueError("El archivo ya existe")
    target.parent.mkdir(parents=True, exist_ok=True)
    src = item_dir / "file"
    if not src.exists():
        raise FileNotFoundError(trash_id)
    shutil.move(str(src), str(target))
    shutil.rmtree(item_dir, ignore_errors=True)
    now = datetime.now(tz=timezone.utc).isoformat()
    size = int(meta.get("size_bytes") or 0)
    _append_audit(
        ws,
        {
            "op": "restore",
            "path": rel,
            "trash_id": trash_id,
            "size_bytes": size,
            "actor": actor,
            "reason": reason,
            "restored_at": now,
        },
    )
    return {"restored": True, "path": rel, "size_bytes": size, "restored_at": now}


def list_audit(session_id: str, limit: int = 50, allow_archived: bool = False) -> list[dict[str, Any]]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    path = _audit_path(ws)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in lines[-max(1, min(limit, 200)) :]:
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                entries.append(item)
        except Exception:
            continue
    return entries


def cleanup_trash(session_id: str, allow_archived: bool = False) -> dict[str, Any]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    items = list_trash(session_id, allow_archived=allow_archived)
    removed = 0
    freed = 0
    for item in items:
        if not item.get("expired"):
            continue
        trash_id = item.get("trash_id")
        if not isinstance(trash_id, str):
            continue
        item_dir = _trash_root(ws) / TRASH_ITEMS_DIR / trash_id
        try:
            shutil.rmtree(item_dir, ignore_errors=True)
            removed += 1
            freed += int(item.get("size_bytes") or 0)
        except Exception:
            continue
    if removed:
        _append_audit(ws, {"op": "purge", "removed": removed, "freed_bytes": freed})
    return {"removed": removed, "freed_bytes": freed}


def cleanup_artifacts(
    session_id: str,
    criteria: dict[str, Any],
    actor: Optional[str] = None,
    allow_archived: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    ws = SessionWorkspace(session_id, allow_archived=allow_archived)
    files = ws.list_files("/")
    min_age_days = criteria.get("min_age_days")
    max_keep = criteria.get("max_keep")
    min_size_bytes = criteria.get("min_size_bytes")
    include_globs = criteria.get("include_globs") or []
    exclude_globs = criteria.get("exclude_globs") or []
    now = datetime.now(tz=timezone.utc)

    def matches_globs(path: str, patterns: list[str]) -> bool:
        if not patterns:
            return True
        return any(fnmatch(path, p) for p in patterns)

    def excluded(path: str) -> bool:
        if not exclude_globs:
            return False
        return any(fnmatch(path, p) for p in exclude_globs)

    candidates: list[dict[str, Any]] = []
    for f in files:
        path = f.get("path")
        if not isinstance(path, str) or _is_protected_path(path):
            continue
        if not matches_globs(path, include_globs):
            continue
        if excluded(path):
            continue
        if min_size_bytes is not None and int(f.get("size_bytes") or 0) < int(min_size_bytes):
            continue
        if min_age_days is not None:
            try:
                modified_at = datetime.fromisoformat(str(f.get("modified_at")))
            except Exception:
                modified_at = None
            if not modified_at:
                continue
            if (now - modified_at) < timedelta(days=int(min_age_days)):
                continue
        candidates.append(f)

    if max_keep is not None and candidates:
        candidates.sort(key=lambda item: item.get("modified_at") or "", reverse=True)
        candidates = candidates[int(max_keep) :]

    deleted: list[dict[str, Any]] = []
    freed = 0
    for item in candidates:
        path = item.get("path")
        if not isinstance(path, str):
            continue
        if dry_run:
            deleted.append({"path": path, "size_bytes": item.get("size_bytes")})
            continue
        try:
            result = delete_artifact(session_id, path, actor=actor, reason="cleanup", allow_archived=allow_archived)
            deleted.append(result)
            freed += int(result.get("freed_bytes") or 0)
        except Exception:
            continue
    if deleted:
        _append_audit(
            ws,
            {
                "op": "cleanup",
                "count": len(deleted),
                "freed_bytes": freed,
                "actor": actor,
                "criteria": criteria,
                "dry_run": dry_run,
            },
        )
    return {"deleted": deleted, "count": len(deleted), "freed_bytes": freed, "dry_run": dry_run}
