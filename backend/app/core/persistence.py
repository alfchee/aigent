import asyncio
import functools
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, create_engine
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