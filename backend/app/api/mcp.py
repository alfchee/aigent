from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from typing import Dict, Any, Optional, List
import json
import os
import re
import time
import httpx
from app.core.mcp_client import McpManager
from app.core.mcp_config import (
    delete_registry_entry,
    delete_server_config,
    get_active_config_public,
    get_active_config_runtime,
    get_registry_merged,
    get_registry_sources,
    set_registry_sources,
    update_registry_entry,
    upsert_server_config,
)

router = APIRouter()

SERVER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
PARAM_RE = re.compile(r"^[a-zA-Z0-9_]+$")


class McpServerDefinition(BaseModel):
    server_id: str
    name: str
    description: str = ""
    command: str
    args: List[str]
    params: List[str] = []
    env_vars: List[str] = []
    source: Optional[str] = None

    @field_validator("server_id")
    @classmethod
    def validate_server_id(cls, value: str) -> str:
        if not SERVER_ID_RE.match(value or ""):
            raise ValueError("server_id inválido")
        return value

    @field_validator("args")
    @classmethod
    def validate_args(cls, value: List[str]) -> List[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("args inválidos")
        return [str(v) for v in value]

    @field_validator("env_vars")
    @classmethod
    def validate_env_vars(cls, value: List[str]) -> List[str]:
        cleaned = []
        for item in value or []:
            name = str(item).strip()
            if not ENV_VAR_RE.match(name):
                raise ValueError(f"env_var inválido: {name}")
            cleaned.append(name)
        return list(dict.fromkeys(cleaned))

    @field_validator("params")
    @classmethod
    def validate_params(cls, value: List[str]) -> List[str]:
        cleaned = []
        for item in value or []:
            name = str(item).strip()
            if not PARAM_RE.match(name):
                raise ValueError(f"param inválido: {name}")
            cleaned.append(name)
        return list(dict.fromkeys(cleaned))


class McpServerConfigRequest(BaseModel):
    server_id: str
    enabled: bool = True
    params: Optional[Dict[str, Any]] = {}
    env_vars: Optional[Dict[str, str]] = {}
    definition: Optional[McpServerDefinition] = None

    @field_validator("server_id")
    @classmethod
    def validate_server_id(cls, value: str) -> str:
        if not SERVER_ID_RE.match(value or ""):
            raise ValueError("server_id inválido")
        return value

    @model_validator(mode="after")
    def validate_definition(self) -> "McpServerConfigRequest":
        if self.definition and self.definition.server_id != self.server_id:
            raise ValueError("definition.server_id no coincide")
        return self


class TestConnectionRequest(BaseModel):
    server_id: str
    params: Optional[Dict[str, Any]] = {}
    env_vars: Optional[Dict[str, str]] = {}
    definition: Optional[McpServerDefinition] = None


class MarketplaceImportRequest(BaseModel):
    source_url: str

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if not value or not value.startswith(("http://", "https://")):
            raise ValueError("URL inválida")
        return value


def _build_registry_item(raw: Any, server_id: str, source: str) -> McpServerDefinition:
    if isinstance(raw, dict):
        payload = dict(raw)
        payload["server_id"] = server_id
        payload["source"] = source
        return McpServerDefinition.model_validate(payload)
    raise ValueError("Definición inválida")


def _resolve_definition(server_id: str, registry: dict[str, Any], inline: Optional[McpServerDefinition]) -> dict[str, Any]:
    if inline:
        return inline.model_dump()
    return registry.get(server_id) or {}


def _validate_config(settings: McpServerConfigRequest, definition: dict[str, Any], existing_env_vars: dict[str, str]) -> None:
    if settings.enabled:
        params = settings.params or {}
        for param in definition.get("params", []) or []:
            if not str(params.get(param, "")).strip():
                raise HTTPException(status_code=422, detail=f"Falta el parámetro {param}")
        env_vars = dict(existing_env_vars)
        for key, value in (settings.env_vars or {}).items():
            if value not in ("", "__masked__"):
                env_vars[key] = value
        for env in definition.get("env_vars", []) or []:
            has_value = bool(env_vars.get(env)) or bool(os.environ.get(env))
            if not has_value:
                raise HTTPException(status_code=422, detail=f"Falta la variable de entorno {env}")


@router.get("/api/mcp/marketplace")
def get_marketplace():
    return get_registry_merged()


@router.get("/api/mcp/marketplace/sources")
def get_marketplace_sources():
    return get_registry_sources()


@router.post("/api/mcp/marketplace/import")
async def import_marketplace(payload: Any = Body(...)):
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    try:
        request = MarketplaceImportRequest.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(request.source_url)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Formato de registry inválido")
    imported = 0
    for server_id, raw in data.items():
        definition = _build_registry_item(raw, str(server_id), request.source_url)
        update_registry_entry(definition.server_id, definition.model_dump())
        imported += 1
    sources = get_registry_sources()
    items = sources.get("sources", [])
    next_sources = [s for s in items if s.get("url") != request.source_url]
    next_sources.append(
        {
            "url": request.source_url,
            "imported_count": imported,
            "last_refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    set_registry_sources({"sources": next_sources})
    return {"status": "success", "imported": imported}


@router.delete("/api/mcp/marketplace/custom/{server_id}")
def delete_custom_definition(server_id: str):
    deleted = delete_registry_entry(server_id)
    if deleted:
        return {"status": "success", "message": f"Registry {server_id} removed."}
    raise HTTPException(status_code=404, detail="Registry not found")


@router.get("/api/mcp/servers")
def get_servers():
    config = get_active_config_public()
    registry = get_registry_merged()
    servers = []
    for server_id, settings in config.get("servers", {}).items():
        server_def = registry.get(server_id, {})
        servers.append(
            {
                "id": server_id,
                "enabled": settings.get("enabled", False),
                "params": settings.get("params", {}),
                "env_vars": settings.get("env_vars", {}),
                "name": server_def.get("name", server_id),
                "description": server_def.get("description", ""),
                "type": server_def.get("source", "custom"),
                "status": "configured",
            }
        )
    return servers


@router.post("/api/mcp/servers")
def save_server(payload: Any = Body(...)):
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    try:
        server = McpServerConfigRequest.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    registry = get_registry_merged()
    definition = _resolve_definition(server.server_id, registry, server.definition)
    if not definition:
        raise HTTPException(status_code=404, detail="Server definition not found")
    if server.definition:
        update_registry_entry(server.definition.server_id, server.definition.model_dump())
        registry = get_registry_merged()
        definition = registry.get(server.server_id, definition)
    existing = get_active_config_runtime().get("servers", {}).get(server.server_id, {})
    existing_env_vars = existing.get("env_vars", {})
    _validate_config(server, definition, existing_env_vars)
    params = server.params if server.params is not None else {}
    env_vars = server.env_vars if server.env_vars is not None else {}
    try:
        upsert_server_config(
            server.server_id,
            {"enabled": server.enabled, "params": params, "env_vars": env_vars},
            keep_masked=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"Server {server.server_id} saved."}


@router.delete("/api/mcp/servers/{server_id}")
def delete_server(server_id: str):
    deleted = delete_server_config(server_id)
    if deleted:
        return {"status": "success", "message": f"Server {server_id} removed."}
    raise HTTPException(status_code=404, detail="Server not found")


@router.post("/api/mcp/test-connection")
async def test_connection(payload: Any = Body(...)):
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    try:
        request = TestConnectionRequest.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    registry = get_registry_merged()
    definition = _resolve_definition(request.server_id, registry, request.definition)
    if not definition:
        raise HTTPException(status_code=404, detail="Server definition not found")
    manager = McpManager()
    params = request.params if request.params is not None else {}
    env_vars = request.env_vars if request.env_vars is not None else {}
    env_vars = {k: v for k, v in env_vars.items() if v not in ("", "__masked__")}
    settings = {"params": params, "env_vars": env_vars}
    result = await manager.test_connection(request.server_id, settings, {request.server_id: definition})
    await manager.cleanup()
    return result
