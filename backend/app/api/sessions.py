import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc

import app.core.filesystem as session_fs
from app.core.persistence import ChatMessage, SessionRecord, ToolCall, db_session, load_chat_messages_page


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _validate_session_id(session_id: str) -> str:
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id vacío")
    if any(ch in sid for ch in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="session_id inválido")
    return sid


class CreateSessionRequest(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: str


def _fallback_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "Nueva Conversación"
    words = cleaned.split(" ")[:5]
    title = " ".join(words).strip()
    return title[:60] or "Nueva Conversación"


async def _generate_title_with_gemini(seed: str) -> Optional[str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        from app.core.config_manager import get_settings

        client = genai.Client(api_key=api_key)
        prompt = (
            "Generate a short Spanish title (3-5 words) for this conversation. "
            "Return only the title, no quotes, no punctuation at the end.\n\n"
            f"Conversation snippet:\n{seed}"
        )
        model_name = get_settings().current_model or "gemini-2.0-flash"
        resp = client.models.generate_content(model=model_name, contents=prompt)
        title = (resp.text or "").strip()
        title = re.sub(r"[\r\n]+", " ", title).strip()
        title = title.strip('"').strip("'").strip()
        if not title:
            return None
        return title[:80]
    except Exception:
        return None


def _session_status(meta_json: Optional[str]) -> dict[str, Optional[str]]:
    try:
        payload = json.loads(meta_json) if meta_json else {}
    except Exception:
        payload = {}
    workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else {}
    status = workspace.get("status")
    archived_at = workspace.get("archived_at")
    return {
        "status": status if isinstance(status, str) else "active",
        "archived_at": archived_at if isinstance(archived_at, str) else None,
    }


@router.get("")
def list_sessions(include_archived: bool = False):
    try:
        try:
            session_fs.auto_archive_inactive_sessions(int(os.getenv("NAVIBOT_ARCHIVE_AFTER_DAYS", "7")))
        except Exception:
            pass
        try:
            session_fs.cleanup_archived_workspaces(int(os.getenv("NAVIBOT_ARCHIVE_RETENTION_DAYS", "30")))
        except Exception:
            pass
        with db_session() as db:
            rows = db.query(SessionRecord).order_by(desc(SessionRecord.updated_at)).limit(200).all()
        items = []
        for r in rows:
            status = _session_status(r.meta_json)
            if status["status"] == "archived" and not include_archived:
                continue
            items.append(
                {
                    "id": r.id,
                    "title": r.title or "Nueva Conversación",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    "status": status["status"],
                    "archived_at": status["archived_at"],
                }
            )
        return {"sessions": items}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error while listing sessions: {str(e)}")


@router.post("")
def create_session(payload: CreateSessionRequest):
    session_id = _validate_session_id(payload.id or f"s_{datetime.utcnow().timestamp():.0f}")
    try:
        with db_session() as db:
            existing = db.get(SessionRecord, session_id)
            if existing is None:
                rec = SessionRecord(id=session_id, title=payload.title or "Nueva Conversación")
                db.add(rec)
            else:
                if payload.title and payload.title.strip():
                    existing.title = payload.title.strip()[:80]
                    existing.updated_at = datetime.now(tz=timezone.utc)
        session_fs.get_workspace_info(session_id)
        return {"id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error while creating session: {str(e)}")


@router.patch("/{session_id}")
def update_session(session_id: str, payload: UpdateSessionRequest):
    sid = _validate_session_id(session_id)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title vacío")
    try:
        with db_session() as db:
            rec = db.get(SessionRecord, sid)
            if rec is None:
                raise HTTPException(status_code=404, detail="Sesión no encontrada")
            rec.title = title[:80]
            rec.updated_at = datetime.now(tz=timezone.utc)
        return {"id": sid, "title": title[:80]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error while updating session: {str(e)}")


@router.delete("/{session_id}")
def delete_session(session_id: str, purge: bool = False):
    sid = _validate_session_id(session_id)
    try:
        if purge:
            with db_session() as db:
                db.query(ChatMessage).filter(ChatMessage.session_id == sid).delete(synchronize_session=False)
                db.query(ToolCall).filter(ToolCall.session_id == sid).delete(synchronize_session=False)
                db.query(SessionRecord).filter(SessionRecord.id == sid).delete(synchronize_session=False)
            try:
                info = session_fs.get_workspace_info(sid)
                ws_dir = Path(info["root"]).resolve()
                import shutil

                shutil.rmtree(ws_dir, ignore_errors=True)
            except Exception:
                pass
            return {"status": "purged"}
        session_fs.archive_session_workspace(sid)
        return {"status": "archived"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error while deleting session: {str(e)}")


@router.get("/{session_id}/workspace")
def get_session_workspace(session_id: str):
    sid = _validate_session_id(session_id)
    try:
        return session_fs.get_workspace_info(sid)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error loading workspace info: {str(e)}")


@router.post("/{session_id}/archive")
def archive_session(session_id: str):
    sid = _validate_session_id(session_id)
    try:
        return session_fs.archive_session_workspace(sid)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error archiving session: {str(e)}")


@router.post("/{session_id}/restore")
def restore_session(session_id: str):
    sid = _validate_session_id(session_id)
    try:
        return session_fs.restore_session_workspace(sid)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error restoring session: {str(e)}")


@router.post("/maintenance")
def run_session_maintenance():
    try:
        archived = session_fs.auto_archive_inactive_sessions(int(os.getenv("NAVIBOT_ARCHIVE_AFTER_DAYS", "7")))
        cleaned = session_fs.cleanup_archived_workspaces(int(os.getenv("NAVIBOT_ARCHIVE_RETENTION_DAYS", "30")))
        return {"archived": archived, "cleaned": cleaned}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error running maintenance: {str(e)}")


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 50, before_id: int | None = None):
    sid = _validate_session_id(session_id)
    try:
        return load_chat_messages_page(session_id=sid, limit=limit, before_id=before_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error while loading session messages: {str(e)}")


@router.post("/{session_id}/autotitle")
async def autotitle_session(session_id: str):
    sid = _validate_session_id(session_id)
    try:
        page = load_chat_messages_page(session_id=sid, limit=20, before_id=None)
        seed = "\n".join([f"{m['role']}: {m['content']}" for m in page.get("items", []) if m.get("content")])[:2000]
        title = await _generate_title_with_gemini(seed)
        if not title:
            title = _fallback_title(seed)

        with db_session() as db:
            rec = db.get(SessionRecord, sid)
            if rec is None:
                rec = SessionRecord(id=sid, title=title)
                db.add(rec)
            else:
                rec.title = title
                rec.updated_at = datetime.now(tz=timezone.utc)

        return {"id": sid, "title": title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error generating title: {str(e)}")
