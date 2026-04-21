from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.mcp_client import mcp_manager
from app.skills.registry import registry

logger = logging.getLogger("navibot.api.mcp")

router = APIRouter(prefix="/mcp", tags=["MCP"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AddServerRequest(BaseModel):
    transport: str = Field(..., description="'stdio' or 'http'")
    # STDIO fields
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    # HTTP/SSE fields
    base_url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class UpdateServerRequest(BaseModel):
    transport: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/servers", summary="List all configured MCP servers with status")
async def list_servers() -> Dict[str, Any]:
    statuses = mcp_manager.get_server_status()
    return {"status": "ok", "servers": statuses}


@router.post("/servers/{server_id}", status_code=201, summary="Add a new MCP server")
async def add_server(server_id: str, body: AddServerRequest) -> Dict[str, Any]:
    try:
        cfg = mcp_manager.add_server(server_id, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # If enabled, connect immediately and register its tools
    if cfg.enabled:
        await _reconnect_and_register(server_id)
    return {"status": "ok", "server_id": server_id, "config": cfg.to_dict()}


@router.put("/servers/{server_id}", summary="Update an existing MCP server config")
async def update_server(server_id: str, body: UpdateServerRequest) -> Dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        cfg = mcp_manager.update_server(server_id, updates)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    # Re-sync to apply the updated config
    await mcp_manager.sync_servers()
    await _refresh_mcp_tools_in_registry()
    return {"status": "ok", "server_id": server_id, "config": cfg.to_dict()}


@router.delete("/servers/{server_id}", summary="Remove an MCP server")
async def remove_server(server_id: str) -> Dict[str, Any]:
    # Disconnect first if active
    await mcp_manager._disconnect_server(server_id)
    # Remove MCP tools for this server from the registry
    _remove_server_tools_from_registry(server_id)
    try:
        mcp_manager.remove_server(server_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return {"status": "ok", "deleted_server_id": server_id}


@router.post(
    "/servers/{server_id}/test",
    summary="Test an MCP server connection (returns tool count)",
)
async def test_server(server_id: str) -> Dict[str, Any]:
    result = await mcp_manager.test_connection(server_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Connection failed."))
    return {"status": "ok", **result}


@router.post(
    "/servers/{server_id}/sync",
    summary="Force-reconnect an MCP server and refresh its tools",
)
async def sync_server(server_id: str) -> Dict[str, Any]:
    if server_id not in mcp_manager._configs:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    # Disconnect and reconnect just this server
    await mcp_manager._disconnect_server(server_id)
    _remove_server_tools_from_registry(server_id)
    await _reconnect_and_register(server_id)
    connected = mcp_manager._servers.get(server_id)
    tool_count = len(connected.tools) if connected else 0
    return {"status": "ok", "server_id": server_id, "tool_count": tool_count}


@router.get("/tools", summary="List all tools from all connected MCP servers")
async def list_tools() -> Dict[str, Any]:
    tools = await mcp_manager.get_all_tools()
    return {
        "status": "ok",
        "tool_count": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "schema": t.args_schema.model_json_schema(),
            }
            for t in tools
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _reconnect_and_register(server_id: str) -> None:
    """Connect a single server and register its tools in the global registry."""
    cfg = mcp_manager._configs.get(server_id)
    if not cfg or not cfg.enabled:
        return
    connected = await mcp_manager._connect_server(cfg)
    if connected:
        mcp_manager._servers[server_id] = connected
    await _refresh_mcp_tools_in_registry()


async def _refresh_mcp_tools_in_registry() -> None:
    """Rebuild all MCP tool entries in the global registry from current connections."""
    # Remove existing MCP tools
    for tool_name in list(registry._tools.keys()):
        if tool_name.startswith("mcp__"):
            del registry._tools[tool_name]
    # Re-register from live connections
    for tool in await mcp_manager.get_all_tools():
        registry.register_dynamic(tool)


def _remove_server_tools_from_registry(server_id: str) -> None:
    """Remove all tools for a specific MCP server from the registry."""
    prefix = f"mcp__{server_id}__"
    for tool_name in [k for k in registry._tools if k.startswith(prefix)]:
        del registry._tools[tool_name]
