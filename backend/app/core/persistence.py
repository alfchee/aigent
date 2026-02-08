import asyncio
import functools
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.runtime_context import get_session_id


Base = declarative_base()
_engine = None
_session_local = None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class SessionRecord(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    title = Column(String, default="Nueva Conversación", nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)
    meta_json = Column(Text, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), index=True, nullable=False)
    tool_name = Column(String, nullable=False)
    args_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


Index("ix_chat_messages_session_created", ChatMessage.session_id, ChatMessage.created_at)
Index("ix_tool_calls_session_created", ToolCall.session_id, ToolCall.created_at)


def get_db_url() -> str:
    return os.getenv("NAVIBOT_DB_URL", "sqlite:///navibot.db")


def get_engine():
    global _engine, _session_local
    if _engine is None:
        url = get_db_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, future=True, connect_args=connect_args)
        _session_local = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    _run_sqlite_migrations(engine)


def _run_sqlite_migrations(engine) -> None:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    try:
        with engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(sessions)")).fetchall()
            col_names = {row[1] for row in cols}
            if "title" not in col_names:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN title VARCHAR"))
    except Exception:
        return


def _get_session() -> Session:
    if _session_local is None:
        get_engine()
    return _session_local()


@contextmanager
def db_session():
    session = _get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_session(db: Session, session_id: str) -> None:
    if not session_id:
        raise ValueError("session_id vacío")
    existing = db.get(SessionRecord, session_id)
    if existing is None:
        db.add(SessionRecord(id=session_id))
    else:
        existing.updated_at = _utcnow()
        if existing.title is None:
            existing.title = "Nueva Conversación"


def _to_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def save_chat_message(session_id: str, role: str, content: Any) -> None:
    """
    Saves a chat message. 
    Content can be a string (legacy) or a Pydantic model/dict (serialized to JSON).
    """
    if hasattr(content, "model_dump_json"):
        content_str = content.model_dump_json()
    elif isinstance(content, (dict, list)):
        content_str = json.dumps(content, ensure_ascii=False, default=str)
    else:
        content_str = str(content)

    with db_session() as db:
        _ensure_session(db, session_id)
        db.add(ChatMessage(session_id=session_id, role=role, content=content_str))


def save_tool_call(
    session_id: str,
    tool_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
    error: Optional[str],
) -> None:
    payload = {"args": list(args), "kwargs": kwargs}
    with db_session() as db:
        _ensure_session(db, session_id)
        db.add(
            ToolCall(
                session_id=session_id,
                tool_name=tool_name,
                args_json=_to_json(payload),
                result_json=_to_json(result),
                error=error,
            )
        )


def load_chat_history(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with db_session() as db:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(limit)
            .all()
        )
    history = []
    for row in rows:
        if row.role == "assistant" or row.role == "model":
            role = "model"
        else:
            role = "user"
            
        try:
            # Try to parse as JSON first (new format)
            data = json.loads(row.content)
            if isinstance(data, dict) and "parts" in data:
                # It's a full Gemini content object
                # Ensure role matches mapped role or use stored role?
                # Gemini SDK expects 'role' and 'parts'.
                # Our DB stores 'assistant'/'user' in role column, but Gemini uses 'model'/'user'.
                # If the JSON has 'role', we can trust it, but we should probably normalize to 'model' if it says 'assistant'.
                
                # If we saved it from Gemini SDK, it has 'model' or 'user'.
                history.append(data)
            else:
                # Fallback for simple JSON or unexpected structure
                history.append({"role": role, "parts": [{"text": row.content}]})
        except (json.JSONDecodeError, TypeError):
            # Legacy text format
            history.append({"role": role, "parts": [{"text": row.content}]})
            
    return history


def _safe_json_loads(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return None


def _extract_text_from_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    out: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            out.append(text)
            continue
        function_call = part.get("function_call")
        if isinstance(function_call, dict) and function_call:
            name = function_call.get("name")
            args = function_call.get("args")
            label = f"[tool_call] {name}" if name else "[tool_call]"
            if args is not None:
                try:
                    out.append(f"{label} {json.dumps(args, ensure_ascii=False, default=str)}")
                except Exception:
                    out.append(f"{label} {str(args)}")
            else:
                out.append(label)
            continue
        function_response = part.get("function_response")
        if isinstance(function_response, dict) and function_response:
            name = function_response.get("name")
            response = function_response.get("response")
            label = f"[tool_result] {name}" if name else "[tool_result]"
            if response is not None:
                try:
                    out.append(f"{label} {json.dumps(response, ensure_ascii=False, default=str)}")
                except Exception:
                    out.append(f"{label} {str(response)}")
            else:
                out.append(label)
            continue
    return "\n".join(out).strip()


def _normalize_chat_row(row: ChatMessage) -> dict[str, Any]:
    if row.role in ("assistant", "model"):
        role = "assistant"
    else:
        role = "user"

    parsed = _safe_json_loads(row.content)
    corrupted = False
    raw: Any = None
    text: str = ""

    if isinstance(parsed, dict) and "parts" in parsed:
        raw = parsed
        raw_role = parsed.get("role")
        if raw_role in ("assistant", "model"):
            role = "assistant"
        elif raw_role == "user":
            role = "user"
        text = _extract_text_from_parts(parsed.get("parts")) or ""
    elif parsed is not None:
        raw = parsed
        text = str(parsed)
    else:
        raw = None
        text = row.content
        if row.content and row.content.lstrip().startswith("{"):
            corrupted = True

    return {
        "id": row.id,
        "session_id": row.session_id,
        "role": role,
        "content": text,
        "raw": raw,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "corrupted": corrupted,
    }


def load_chat_messages_page(
    session_id: str,
    limit: int = 50,
    before_id: Optional[int] = None,
) -> dict[str, Any]:
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    with db_session() as db:
        q = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
        if before_id is not None:
            q = q.filter(ChatMessage.id < before_id)
        rows = q.order_by(ChatMessage.id.desc()).limit(limit + 1).all()

    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()

    items = [_normalize_chat_row(r) for r in rows]
    next_before_id = items[0]["id"] if items else before_id
    return {
        "session_id": session_id,
        "items": items,
        "has_more": has_more,
        "next_before_id": next_before_id,
        "limit": limit,
    }


def wrap_tool(tool):
    if getattr(tool, "_navibot_wrapped", False):
        return tool
    is_async = asyncio.iscoroutinefunction(tool)

    if is_async:
        @functools.wraps(tool)
        async def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                result = await tool(*args, **kwargs)
                save_tool_call(session_id, tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.__name__, args, kwargs, None, str(e))
                raise
    else:
        @functools.wraps(tool)
        def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                result = tool(*args, **kwargs)
                save_tool_call(session_id, tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.__name__, args, kwargs, None, str(e))
                raise

    wrapped._navibot_wrapped = True
    return wrapped
