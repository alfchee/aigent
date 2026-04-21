from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

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

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        if v not in ("stdio", "http", "sse"):
            raise ValueError("transport must be 'stdio', 'http', or 'sse'")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_http_required_fields(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("transport") in ("http", "sse") and not v:
            raise ValueError("base_url is required for HTTP/SSE transport")
        return v

    @field_validator("command")
    @classmethod
    def validate_stdio_required_fields(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("transport") == "stdio" and not v:
            raise ValueError("command is required for STDIO transport")
        return v


class UpdateServerRequest(BaseModel):
    transport: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("stdio", "http", "sse"):
            raise ValueError("transport must be 'stdio', 'http', or 'sse'")
        return v


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
        try:
            await _reconnect_and_register(server_id)
        except Exception as exc:
            logger.error(f"Failed to connect new server '{server_id}': {exc}")
            raise HTTPException(
                status_code=502,
                detail=f"Server added but connection failed: {str(exc)}"
            )
    # Mask secrets before returning config to the caller
    return {"status": "ok", "server_id": server_id, "config": cfg.to_safe_dict()}


@router.put("/servers/{server_id}", summary="Update an existing MCP server config")
async def update_server(server_id: str, body: UpdateServerRequest) -> Dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        cfg = mcp_manager.update_server(server_id, updates)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Re-sync all servers to apply the updated config, then refresh tools
    try:
        await mcp_manager.sync_servers()
        await _refresh_mcp_tools_in_registry()
    except Exception as exc:
        logger.error(f"Failed to sync server '{server_id}': {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Config updated but sync failed: {str(exc)}"
        )
    # Mask secrets before returning config to the caller
    return {"status": "ok", "server_id": server_id, "config": cfg.to_safe_dict()}


@router.delete("/servers/{server_id}", summary="Remove an MCP server")
async def remove_server(server_id: str) -> Dict[str, Any]:
    try:
        await mcp_manager.disconnect_and_remove_server(server_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    # Remove tools from registry after successful removal
    registry.remove_tools_by_prefix(f"mcp__{server_id}__")
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
    if server_id not in mcp_manager.get_server_status():
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    try:
        await mcp_manager.reconnect_server(server_id)
        await _refresh_mcp_tools_in_registry()
    except Exception as exc:
        logger.error(f"Failed to sync server '{server_id}': {exc}")
        raise HTTPException(status_code=502, detail=f"Sync failed: {str(exc)}")
    # Count tools currently registered for this server
    tool_count = len([n for n in registry._tools if n.startswith(f"mcp__{server_id}__")])
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
    """Reconnect a single server (via public API) and refresh all MCP tools."""
    await mcp_manager.reconnect_server(server_id)
    await _refresh_mcp_tools_in_registry()


async def _refresh_mcp_tools_in_registry() -> None:
    """Rebuild all MCP tool entries in the global registry from current connections."""
    # Remove existing MCP tools
    registry.remove_tools_by_prefix("mcp__")
    # Re-register from live connections
    for tool in await mcp_manager.get_all_tools():
        registry.register_dynamic(tool)
