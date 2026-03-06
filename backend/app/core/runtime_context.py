from __future__ import annotations

import asyncio
import os
from contextvars import ContextVar
from typing import Awaitable, Callable, Optional
from enum import Enum

SessionId = str
MemoryUserId = str
EventCallback = Callable[[str, dict], Awaitable[None]]

# Ghost User Pattern: Identify non-human scheduler entities
class EntityType(Enum):
    HUMAN = "human"
    SCHEDULER = "scheduler"
    API = "api"
    UNKNOWN = "unknown"

_session_id_var: ContextVar[SessionId] = ContextVar("navibot_session_id", default="default")
_memory_user_id_var: ContextVar[MemoryUserId] = ContextVar("navibot_memory_user_id", default="default")
_event_callback_var: ContextVar[Optional[EventCallback]] = ContextVar("navibot_event_callback", default=None)
_request_id_var: ContextVar[str] = ContextVar("navibot_request_id", default="")
_entity_type_var: ContextVar[EntityType] = ContextVar("navibot_entity_type", default=EntityType.HUMAN)
_entity_metadata_var: ContextVar[dict] = ContextVar("navibot_entity_metadata", default={})


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
    
    # Check context var first (priority over env/session)
    context_candidate = get_memory_user_id()
    if context_candidate and context_candidate != "default":
        return context_candidate
        
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


def get_entity_type() -> EntityType:
    """Get the current entity type (human, scheduler, api, etc.)"""
    return _entity_type_var.get()


def set_entity_type(entity_type: EntityType) -> None:
    """Set the entity type for the current context"""
    _entity_type_var.set(entity_type)


def reset_entity_type(token) -> None:
    """Reset entity type to default"""
    _entity_type_var.reset(token)


def get_entity_metadata() -> dict:
    """Get metadata about the current entity"""
    return _entity_metadata_var.get().copy()


def set_entity_metadata(metadata: dict) -> None:
    """Set metadata for the current entity"""
    _entity_metadata_var.set(metadata or {})


def reset_entity_metadata(token) -> None:
    """Reset entity metadata to default"""
    _entity_metadata_var.reset(token)


def is_scheduler_entity() -> bool:
    """Check if the current entity is a scheduler (ghost user)"""
    return get_entity_type() == EntityType.SCHEDULER


def is_human_entity() -> bool:
    """Check if the current entity is a human user"""
    return get_entity_type() == EntityType.HUMAN


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
