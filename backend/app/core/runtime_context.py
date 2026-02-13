from __future__ import annotations

import asyncio
import os
from contextvars import ContextVar
from typing import Awaitable, Callable, Optional

SessionId = str
MemoryUserId = str
EventCallback = Callable[[str, dict], Awaitable[None]]

_session_id_var: ContextVar[SessionId] = ContextVar("navibot_session_id", default="default")
_memory_user_id_var: ContextVar[MemoryUserId] = ContextVar("navibot_memory_user_id", default="default")
_event_callback_var: ContextVar[Optional[EventCallback]] = ContextVar("navibot_event_callback", default=None)
_request_id_var: ContextVar[str] = ContextVar("navibot_request_id", default="")


def get_session_id() -> SessionId:
    return _session_id_var.get()


def set_session_id(session_id: SessionId):
    return _session_id_var.set(session_id or "default")


def reset_session_id(token) -> None:
    _session_id_var.reset(token)


def get_memory_user_id() -> MemoryUserId:
    return _memory_user_id_var.get()


def set_memory_user_id(memory_user_id: MemoryUserId):
    return _memory_user_id_var.set(memory_user_id or "default")


def reset_memory_user_id(token) -> None:
    _memory_user_id_var.reset(token)


def resolve_memory_user_id(explicit: Optional[str], session_id: Optional[str], header_value: Optional[str] = None) -> MemoryUserId:
    candidate = (explicit or "").strip()
    if candidate:
        return candidate
    header_candidate = (header_value or "").strip()
    if header_candidate:
        return header_candidate
    env_candidate = (os.getenv("NAVIBOT_MEMORY_USER_ID") or "").strip()
    if env_candidate:
        return env_candidate
    return (session_id or "default").strip() or "default"


def get_event_callback() -> Optional[EventCallback]:
    return _event_callback_var.get()


def set_event_callback(callback: Optional[EventCallback]):
    return _event_callback_var.set(callback)


def reset_event_callback(token) -> None:
    _event_callback_var.reset(token)


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str):
    return _request_id_var.set(request_id or "")


def reset_request_id(token) -> None:
    _request_id_var.reset(token)


def emit_event(event_type: str, data: dict) -> None:
    try:
        from app.core.artifact_events import publish

        if event_type == "artifact":
            publish(get_session_id(), event_type, data)
    except Exception:
        pass

    callback = get_event_callback()
    if not callback:
        return
    payload = data
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(callback(event_type, payload))
    except RuntimeError:
        try:
            asyncio.run(callback(event_type, payload))
        except Exception:
            return
