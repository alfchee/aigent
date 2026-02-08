import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.core.artifact_events import subscribe, unsubscribe


router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@router.get("/api/artifacts/events")
async def artifacts_events(request: Request, session_id: str = "default"):
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
