from fastapi import APIRouter, HTTPException, Body, status
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, Optional, List
import json
import os
from app.core.mcp_client import McpManager

router = APIRouter()

class McpServerConfig(BaseModel):
    server_id: str
    enabled: bool = True
    params: Optional[Dict[str, Any]] = {}
    env_vars: Optional[Dict[str, str]] = {}
    # Optional fields for custom servers if needed later
    command: Optional[str] = None
    args: Optional[List[str]] = None

class TestConnectionRequest(BaseModel):
    server_id: str
    params: Optional[Dict[str, Any]] = {}
    env_vars: Optional[Dict[str, str]] = {}

    class Config:
        arbitrary_types_allowed = True

def _get_paths():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return {
        "registry": os.path.join(root, "app/data/mcp_registry.json"),
        "config": os.path.join(root, "app/settings/active_mcp.json")
    }

def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

@router.get("/api/mcp/marketplace")
def get_marketplace():
    """Devuelve la lista de servidores soportados (registry)."""
    paths = _get_paths()
    return _load_json(paths["registry"])

@router.get("/api/mcp/servers")
def get_servers():
    """Devuelve la configuración actual de los servidores."""
    paths = _get_paths()
    config = _load_json(paths["config"])
    registry = _load_json(paths["registry"])
    
    # Merge config with registry info for better UI display
    servers = []
    for server_id, settings in config.items():
        server_data = {
            "id": server_id,
            "enabled": settings.get("enabled", False),
            "params": settings.get("params", {}),
            "env_vars": settings.get("env_vars", {}),
            # Add registry info if available
            "name": registry.get(server_id, {}).get("name", server_id),
            "type": server_id if server_id in registry else "custom",
            "status": "configured" # Frontend can poll actual status if needed
        }
        servers.append(server_data)
    return servers

@router.post("/api/mcp/servers")
def save_server(payload: Any = Body(...)):
    """Añade o actualiza la configuración de un servidor MCP."""
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    try:
        server = McpServerConfig.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    paths = _get_paths()
    config = _load_json(paths["config"])
    params = server.params if server.params is not None else {}
    env_vars = server.env_vars if server.env_vars is not None else {}
    
    # Update config
    config[server.server_id] = {
        "enabled": server.enabled,
        "params": params,
        "env_vars": env_vars
    }
    
    # If custom command provided, save it too (future proofing)
    if server.command:
        config[server.server_id]["command"] = server.command
    if server.args:
        config[server.server_id]["args"] = server.args
        
    _save_json(paths["config"], config)
    return {"status": "success", "message": f"Server {server.server_id} saved."}

@router.delete("/api/mcp/servers/{server_id}")
def delete_server(server_id: str):
    """Elimina la configuración de un servidor MCP."""
    paths = _get_paths()
    config = _load_json(paths["config"])
    
    if server_id in config:
        del config[server_id]
        _save_json(paths["config"], config)
        return {"status": "success", "message": f"Server {server_id} removed."}
    
    raise HTTPException(status_code=404, detail="Server not found")

@router.post("/api/mcp/test-connection")
async def test_connection(payload: Any = Body(...)):
    """Prueba la conexión con un servidor MCP."""
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    try:
        request = TestConnectionRequest.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    paths = _get_paths()
    registry = _load_json(paths["registry"])
    manager = McpManager()
    
    # Ensure params/env_vars are dicts even if None provided
    params = request.params if request.params is not None else {}
    env_vars = request.env_vars if request.env_vars is not None else {}
    
    settings = {"params": params, "env_vars": env_vars}
    result = await manager.test_connection(request.server_id, settings, registry)
    await manager.cleanup()
    return result
