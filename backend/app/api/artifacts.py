import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.artifact_events import subscribe, unsubscribe
from app.core.filesystem import cleanup_artifacts, cleanup_trash, delete_artifact, list_audit, list_trash, restore_artifact
from app.core.runtime_context import emit_event


router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class DeleteArtifactRequest(BaseModel):
    session_id: str
    path: str
    reason: Optional[str] = None
    actor: Optional[str] = None
    allow_archived: bool = False


class RestoreArtifactRequest(BaseModel):
    session_id: str
    trash_id: str
    actor: Optional[str] = None
    reason: Optional[str] = None
    allow_archived: bool = False


class CleanupArtifactsRequest(BaseModel):
    session_id: str
    min_age_days: Optional[int] = None
    max_keep: Optional[int] = None
    min_size_bytes: Optional[int] = None
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)
    allow_archived: bool = False
    actor: Optional[str] = None
    dry_run: bool = False
    purge_expired_trash: bool = False



@router.get("/api/artifacts/events")
async def artifacts_events(request: Request, session_id: str):
    queue = subscribe(session_id)

    async def gen():
        try:
            yield {"event": "ready", "data": json.dumps({"session_id": session_id, "timestamp": _utc_now_iso()})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": json.dumps({"timestamp": _utc_now_iso()})}
                    continue
                yield {"event": item["event"], "data": json.dumps(item["data"])}
        finally:
            unsubscribe(session_id, queue)

    return EventSourceResponse(gen())


@router.get("/api/artifacts/trash")
async def get_trash(session_id: str, allow_archived: bool = False):
    try:
        items = list_trash(session_id, allow_archived=allow_archived)
        return {"session_id": session_id, "items": items}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/api/artifacts/audit")
async def get_audit(session_id: str, limit: int = 50, allow_archived: bool = False):
    try:
        items = list_audit(session_id, limit=limit, allow_archived=allow_archived)
        return {"session_id": session_id, "items": items}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/api/artifacts/delete")
async def delete_artifact_endpoint(payload: DeleteArtifactRequest):
    try:
        result = delete_artifact(
            payload.session_id,
            payload.path,
            actor=payload.actor,
            reason=payload.reason,
            allow_archived=payload.allow_archived,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    emit_event(
        "artifact",
        {
            "session_id": payload.session_id,
            "op": "delete",
            "path": payload.path,
            "trash_id": result.get("trash_id"),
            "freed_bytes": result.get("freed_bytes"),
            "restore_until": result.get("restore_until"),
        },
    )
    return result


@router.post("/api/artifacts/restore")
async def restore_artifact_endpoint(payload: RestoreArtifactRequest):
    try:
        result = restore_artifact(
            payload.session_id,
            payload.trash_id,
            actor=payload.actor,
            reason=payload.reason,
            allow_archived=payload.allow_archived,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en papelera")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    emit_event(
        "artifact",
        {
            "session_id": payload.session_id,
            "op": "restore",
            "path": result.get("path"),
            "trash_id": payload.trash_id,
            "size_bytes": result.get("size_bytes"),
        },
    )
    return result


@router.post("/api/artifacts/cleanup")
async def cleanup_artifacts_endpoint(payload: CleanupArtifactsRequest):
    criteria = {
        "min_age_days": payload.min_age_days,
        "max_keep": payload.max_keep,
        "min_size_bytes": payload.min_size_bytes,
        "include_globs": payload.include_globs,
        "exclude_globs": payload.exclude_globs,
    }
    try:
        result = cleanup_artifacts(
            payload.session_id,
            criteria,
            actor=payload.actor,
            allow_archived=payload.allow_archived,
            dry_run=payload.dry_run,
        )
        trash_result = None
        if payload.purge_expired_trash:
            trash_result = cleanup_trash(payload.session_id, allow_archived=payload.allow_archived)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    emit_event(
        "artifact",
        {
            "session_id": payload.session_id,
            "op": "cleanup",
            "count": result.get("count"),
            "freed_bytes": result.get("freed_bytes"),
            "dry_run": payload.dry_run,
        },
    )
    return {**result, "trash": trash_result}
