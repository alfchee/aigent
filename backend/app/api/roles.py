from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.roles import AgentRole, role_manager
from app.core.agent_graph import get_sessions_using_role, rebuild_graph
from app.core.llm import ModelConfig, default_llm

logger = logging.getLogger("navibot.api.roles")

router = APIRouter(prefix="/roles", tags=["Roles"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateRoleRequest(BaseModel):
    role_id: str
    name: str
    description: str
    model: str = "gpt-4o"
    provider_override: Optional[str] = None
    system_prompt: str
    skills: List[str] = []
    mcp_servers: List[str] = []
    enabled: bool = True


class UpdateRoleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    provider_override: Optional[str] = None
    system_prompt: Optional[str] = None
    skills: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    enabled: Optional[bool] = None


class TestRoleRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", summary="List all worker roles")
async def list_roles() -> Dict[str, Any]:
    snapshot = role_manager.snapshot()
    return {
        "status": "ok",
        "config_path": snapshot.config_path,
        "updated_at": snapshot.updated_at,
        "supervisor": snapshot.supervisor.model_dump(),
        "workers": [w.model_dump(mode="json") for w in snapshot.workers],
    }


@router.get("/{role_id}", summary="Get a single worker role by ID")
async def get_role(role_id: str) -> Dict[str, Any]:
    try:
        role = role_manager.get_role(role_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found.")
    return {"status": "ok", "role": role.model_dump(mode="json")}


@router.post("", status_code=201, summary="Create a new worker role")
async def create_role(body: CreateRoleRequest) -> Dict[str, Any]:
    role = AgentRole(**body.model_dump())
    try:
        created = role_manager.create_role(role)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    rebuild_graph()
    logger.info("Role '%s' created; graph rebuilt.", created.role_id)
    return {"status": "ok", "role": created.model_dump(mode="json")}


@router.put("/{role_id}", summary="Update an existing worker role")
async def update_role(role_id: str, body: UpdateRoleRequest) -> Dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = role_manager.update_role(role_id, updates)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found.")
    rebuild_graph()
    logger.info("Role '%s' updated; graph rebuilt.", role_id)
    return {"status": "ok", "role": updated.model_dump(mode="json")}


@router.delete("/{role_id}", status_code=200, summary="Delete a worker role")
async def delete_role(role_id: str) -> Dict[str, Any]:
    active = get_sessions_using_role(role_id)
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Role '{role_id}' is referenced by active sessions: {active}. "
                   "Wait for those sessions to finish or start new sessions.",
        )
    try:
        role_manager.delete_role(role_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found.")
    rebuild_graph()
    logger.info("Role '%s' deleted; graph rebuilt.", role_id)
    return {"status": "ok", "deleted_role_id": role_id}


@router.post("/{role_id}/test", summary="Send a test message to a worker role")
async def test_role(role_id: str, body: TestRoleRequest) -> Dict[str, Any]:
    try:
        role = role_manager.get_role(role_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found.")

    messages = [
        {"role": "system", "content": role.system_prompt},
        {"role": "user", "content": body.message},
    ]
    worker_config = ModelConfig(
        provider=default_llm.default_config.provider,
        model_name=role.model,
        temperature=default_llm.default_config.temperature,
        max_tokens=default_llm.default_config.max_tokens,
        api_key=default_llm.default_config.api_key,
        base_url=default_llm.default_config.base_url,
    )
    try:
        response = await default_llm.generate(messages=messages, config=worker_config)
        reply = response.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("test_role: LLM call failed for role '%s'", role_id)
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    return {"status": "ok", "role_id": role_id, "message": body.message, "response": reply}


@router.post("/reload", summary="Hot-reload roles from roles.json")
async def reload_roles() -> Dict[str, Any]:
    snapshot = role_manager.reload()
    rebuild_graph()
    return {
        "status": "ok",
        "config_path": snapshot.config_path,
        "updated_at": snapshot.updated_at,
        "workers_count": len(snapshot.workers),
    }
