from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.paths import workspace_db_dir, workspace_root

router = APIRouter()


def _chat_db_path() -> Path:
    return workspace_db_dir() / "chat_messages.db"


def _episodic_db_path() -> Path:
    return workspace_db_dir() / "episodic_memory.db"


def _workspace_sessions_dir() -> Path:
    return workspace_root() / "sessions"


def _shorten(text: str, limit: int = 80) -> str:
    clean = " ".join((text or "").split())
    return clean[:limit] if len(clean) > limit else clean


def _load_latest_summary(session_id: str) -> str | None:
    db = _episodic_db_path()
    if not db.exists():
        return None
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                """
                SELECT summary
                FROM session_summaries
                WHERE session_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if not row or not row[0]:
                return None
            return _shorten(str(row[0]), 120)
    except Exception:
        return None


def _load_db_sessions() -> dict[str, dict[str, Any]]:
    db = _chat_db_path()
    if not db.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            """
            SELECT session_id, MAX(created_at) AS last_activity, COUNT(*) AS total_messages
            FROM chat_messages
            GROUP BY session_id
            """
        ).fetchall()
        for session_id, last_activity, total_messages in rows:
            first_user = conn.execute(
                """
                SELECT text
                FROM chat_messages
                WHERE session_id = ? AND role = 'user'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            latest = conn.execute(
                """
                SELECT text
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            latest_conversation = conn.execute(
                """
                SELECT conversation_id
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            title_candidate = (first_user[0] if first_user else "") or (latest[0] if latest else "")
            result[session_id] = {
                "session_id": session_id,
                "title": _shorten(str(title_candidate) or f"Sesión {session_id[:8]}", 56),
                "last_activity": int(last_activity or 0),
                "total_messages": int(total_messages or 0),
                "last_message_preview": _shorten(str(latest[0]) if latest else "", 120),
                "last_conversation_id": str(latest_conversation[0]) if latest_conversation else session_id,
                "summary": _load_latest_summary(session_id),
                "source": "db",
            }
    return result


def _merge_workspace_sessions(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    sessions_dir = _workspace_sessions_dir()
    if not sessions_dir.exists():
        return items

    for child in sessions_dir.iterdir():
        if not child.is_dir():
            continue
        session_id = child.name
        state_file = child / "state.json"
        state_payload: dict[str, Any] = {}
        ts = int(child.stat().st_mtime * 1000)
        if state_file.exists():
            ts = int(state_file.stat().st_mtime * 1000)
            try:
                state_payload = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                state_payload = {}

        if session_id not in items:
            items[session_id] = {
                "session_id": session_id,
                "title": _shorten(str(state_payload.get("title") or f"Sesión {session_id[:8]}"), 56),
                "last_activity": ts,
                "total_messages": 0,
                "last_message_preview": _shorten(str(state_payload.get("last_message") or ""), 120),
                "last_conversation_id": str(state_payload.get("conversation_id") or session_id),
                "summary": _load_latest_summary(session_id),
                "source": "workspace",
            }
    return items


def list_session_summaries() -> list[dict[str, Any]]:
    merged = _merge_workspace_sessions(_load_db_sessions())
    rows = list(merged.values())
    rows.sort(key=lambda item: item.get("last_activity", 0), reverse=True)
    return rows


@router.get("/sessions")
async def get_sessions():
    items = list_session_summaries()
    return {"status": "ok", "count": len(items), "items": items}
