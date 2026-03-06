import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.channels.config import get_channel_config, get_channels_config
from app.channels.events import subscribe, unsubscribe
from app.channels.manager import channel_manager


router = APIRouter(tags=["channels"])


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class ChannelValidateRequest(BaseModel):
    channel_id: str
    settings: dict[str, Any] = {}
    check_connection: bool = False


class ChannelToggleRequest(BaseModel):
    channel_id: str
    settings: dict[str, Any] = {}


@router.get("/api/channels")
async def list_channels():
    specs = channel_manager.list_specs()
    statuses = {s["channel_id"]: s for s in channel_manager.list_statuses()}
    cfg = get_channels_config()
    channels_cfg = cfg.get("channels") if isinstance(cfg, dict) else {}
    if not isinstance(channels_cfg, dict):
        channels_cfg = {}
    payload = []
    for spec in specs:
        channel_id = spec["channel_id"]
        entry = channels_cfg.get(channel_id) if isinstance(channels_cfg, dict) else None
        enabled = isinstance(entry, dict) and entry.get("enabled") is True
        payload.append(
            {
                **spec,
                "enabled": enabled,
                "settings": entry.get("settings") if isinstance(entry, dict) else {},
                "status": statuses.get(channel_id),
            }
        )
    return {"channels": payload}


@router.post("/api/channels/validate")
async def validate_channel(payload: ChannelValidateRequest):
    errors = await channel_manager.validate_channel(payload.channel_id, payload.settings, payload.check_connection)
    return {"channel_id": payload.channel_id, "valid": len(errors) == 0, "errors": errors}


@router.post("/api/channels/enable")
async def enable_channel(payload: ChannelToggleRequest):
    try:
        result = await channel_manager.enable_channel(payload.channel_id, payload.settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/api/channels/disable")
async def disable_channel(payload: ChannelToggleRequest):
    result = await channel_manager.disable_channel(payload.channel_id)
    return result


@router.get("/api/channels/events")
async def channels_events(request: Request):
    queue = subscribe("channels")

    async def gen():
        try:
            yield {"event": "ready", "data": json.dumps({"timestamp": _utc_now_iso()})}
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
            unsubscribe("channels", queue)

    return EventSourceResponse(gen())
