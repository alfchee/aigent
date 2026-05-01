"""MCP Client — manages connections to Model Context Protocol servers.

Supports STDIO (local process) and HTTP/SSE (remote) transports.
Tools exposed by connected servers are wrapped as ToolDefinition objects
compatible with ToolRegistry.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.types import Tool as McpTool

from app.core.paths import workspace_config_dir
from app.skills.registry import ToolDefinition

logger = logging.getLogger("navibot.core.mcp_client")

_MCP_CONFIG_FILE = "mcp_config.json"
_MCP_CONNECT_TIMEOUT = 10.0  # seconds


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------

class McpServerConfig:
    """Parsed representation of one entry in mcp_config.json."""

    def __init__(self, server_id: str, data: Dict[str, Any]) -> None:
        self.server_id: str = server_id
        self.enabled: bool = data.get("enabled", True)
        self.transport: str = data.get("transport", "stdio")
        # STDIO fields
        self.command: str = data.get("command", "")
        self.args: List[str] = data.get("args", [])
        self.env_vars: Dict[str, str] = data.get("env_vars", {})
        # HTTP / SSE fields
        self.base_url: str = data.get("base_url", "")
        self.headers: Dict[str, str] = data.get("headers", {})
        # Validate secret fields
        self._validate_secrets()

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "enabled": self.enabled,
            "transport": self.transport,
        }
        if self.transport == "stdio":
            d["command"] = self.command
            d["args"] = self.args
            d["env_vars"] = self.env_vars
        else:
            d["base_url"] = self.base_url
            d["headers"] = self.headers
        return d

    def _validate_secrets(self) -> None:
        """Validate that env_vars and headers contain only string keys and values."""
        if not isinstance(self.env_vars, dict):
            raise ValueError(f"env_vars must be a dict, got {type(self.env_vars).__name__}")
        for key, value in self.env_vars.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(
                    f"env_vars keys and values must be strings; got {type(key).__name__}={type(value).__name__}"
                )

        if not isinstance(self.headers, dict):
            raise ValueError(f"headers must be a dict, got {type(self.headers).__name__}")
        for key, value in self.headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(
                    f"headers keys and values must be strings; got {type(key).__name__}={type(value).__name__}"
                )

    def to_safe_dict(self) -> Dict[str, Any]:
        """Like to_dict() but masks non-empty secret values (env_vars, headers)."""
        d = self.to_dict()
        if "env_vars" in d:
            d["env_vars"] = {k: ("***" if v else "") for k, v in d["env_vars"].items()}
        if "headers" in d:
            d["headers"] = {k: ("***" if v else "") for k, v in d["headers"].items()}
        return d


# ---------------------------------------------------------------------------
# Connected server wrapper
# ---------------------------------------------------------------------------

class ConnectedServer:
    """Holds a live MCP ClientSession together with its listed tools."""

    def __init__(
        self,
        server_id: str,
        session: ClientSession,
        tools: List[McpTool],
        exit_stack: AsyncExitStack,
    ) -> None:
        self.server_id = server_id
        self.session = session
        self.tools = tools
        self._exit_stack = exit_stack


# ---------------------------------------------------------------------------
# Helper: build a callable that calls a specific MCP tool on a session
# ---------------------------------------------------------------------------

def _make_tool_func(session: ClientSession, mcp_name: str) -> Callable:
    async def _call(**kwargs: Any) -> str:
        result = await session.call_tool(mcp_name, arguments=kwargs or {})
        parts: List[str] = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                logger.warning(
                    "MCP tool %r returned content without .text attribute: %s",
                    mcp_name, type(content).__name__
                )
                parts.append(str(content))
        return "\n".join(parts)

    _call.__name__ = f"mcp_{mcp_name}"
    return _call


# ---------------------------------------------------------------------------
# McpManager
# ---------------------------------------------------------------------------

class McpManager:
    """
    Manages lifecycle of MCP server connections and exposes their tools
    as ToolDefinition objects for ToolRegistry.

    Tool names follow the convention: ``mcp__{server_id}__{original_name}``
    which prevents collisions and allows per-role filtering.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path: Path = config_path or (workspace_config_dir() / _MCP_CONFIG_FILE)
        self._servers: Dict[str, ConnectedServer] = {}
        self._configs: Dict[str, McpServerConfig] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Config I/O
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, McpServerConfig]:
        if not self._config_path.exists():
            logger.info(
                "mcp_config.json not found at %s — MCP disabled.", self._config_path
            )
            return {}
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse mcp_config.json (corrupted file, skipping): %s", exc
            )
            return {}
        except Exception as exc:
            logger.error("Unexpected error reading mcp_config.json: %s", exc)
            return {}
        return {
            sid: McpServerConfig(sid, sdata)
            for sid, sdata in raw.get("servers", {}).items()
        }

    def _save_config(self) -> None:
        """Write _configs back to mcp_config.json atomically."""
        data = {"servers": {sid: cfg.to_dict() for sid, cfg in self._configs.items()}}
        config_dir = self._config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(self._config_path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def connect_stdio(
        self,
        server_id: str,
        command: str,
        args: List[str],
        env: Dict[str, str],
    ) -> ConnectedServer:
        """Connect to a local STDIO MCP server with timeout."""
        async def _connect():
            merged_env = {**os.environ, **env}
            params = StdioServerParameters(command=command, args=args, env=merged_env)
            stack = AsyncExitStack()
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools_result = await session.list_tools()
            tools = tools_result.tools
            return ConnectedServer(
                server_id=server_id, session=session, tools=tools, exit_stack=stack
            )

        try:
            connected = await asyncio.wait_for(_connect(), timeout=_MCP_CONNECT_TIMEOUT)
            logger.info(
                "MCP STDIO connected: server=%s tools=%d", server_id, len(connected.tools)
            )
            return connected
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Failed to connect to STDIO server '{server_id}' within {_MCP_CONNECT_TIMEOUT}s"
            )

    async def connect_http(
        self,
        server_id: str,
        base_url: str,
        headers: Dict[str, str],
    ) -> ConnectedServer:
        """Connect to a remote MCP server via HTTP/SSE transport with timeout."""
        async def _connect():
            stack = AsyncExitStack()
            read, write = await stack.enter_async_context(
                sse_client(url=base_url, headers=headers)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools_result = await session.list_tools()
            tools = tools_result.tools
            return ConnectedServer(
                server_id=server_id, session=session, tools=tools, exit_stack=stack
            )

        try:
            connected = await asyncio.wait_for(_connect(), timeout=_MCP_CONNECT_TIMEOUT)
            logger.info(
                "MCP HTTP/SSE connected: server=%s tools=%d", server_id, len(connected.tools)
            )
            return connected
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Failed to connect to HTTP/SSE server '{server_id}' within {_MCP_CONNECT_TIMEOUT}s"
            )

    async def _connect_server(
        self, cfg: McpServerConfig
    ) -> Optional[ConnectedServer]:
        # Validate required fields before attempting any OS/network call
        if cfg.transport == "stdio" and not cfg.command.strip():
            logger.warning(
                "Skipping MCP server '%s': stdio transport requires a non-empty 'command'",
                cfg.server_id,
            )
            return None
        if cfg.transport in ("http", "sse") and not cfg.base_url.strip():
            logger.warning(
                "Skipping MCP server '%s': http/sse transport requires a non-empty 'base_url'",
                cfg.server_id,
            )
            return None

        try:
            if cfg.transport == "stdio":
                return await self.connect_stdio(
                    cfg.server_id, cfg.command, cfg.args, cfg.env_vars
                )
            elif cfg.transport in ("http", "sse"):
                return await self.connect_http(
                    cfg.server_id, cfg.base_url, cfg.headers
                )
            else:
                logger.warning(
                    "Unknown transport '%s' for server '%s'",
                    cfg.transport,
                    cfg.server_id,
                )
                return None
        except Exception as exc:
            logger.error(
                "Failed to connect MCP server '%s': %s", cfg.server_id, exc
            )
            return None

    async def _disconnect_server(self, server_id: str) -> None:
        connected = self._servers.pop(server_id, None)
        if connected:
            try:
                await connected._exit_stack.aclose()
            except Exception as exc:
                logger.warning(
                    "Error disconnecting MCP server '%s': %s", server_id, exc
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_servers(self) -> None:
        """Read mcp_config.json and connect/disconnect servers as needed."""
        async with self._lock:
            self._configs = self._load_config()
            # Disconnect removed or disabled servers
            for sid in list(self._servers.keys()):
                cfg = self._configs.get(sid)
                if not cfg or not cfg.enabled:
                    await self._disconnect_server(sid)
            # Connect new enabled servers
            for sid, cfg in self._configs.items():
                if not cfg.enabled:
                    continue
                if sid not in self._servers:
                    connected = await self._connect_server(cfg)
                    if connected:
                        self._servers[sid] = connected

    async def get_all_tools(self) -> List[ToolDefinition]:
        """Return all MCP tools wrapped as ToolDefinition objects."""
        from pydantic import create_model

        # Snapshot the live servers under the lock; build ToolDefinitions outside it
        async with self._lock:
            snapshot = [
                (server_id, list(connected.tools), connected.session)
                for server_id, connected in self._servers.items()
            ]

        result: List[ToolDefinition] = []
        for server_id, tools, session in snapshot:
            for mcp_tool in tools:
                tool_name = f"mcp__{server_id}__{mcp_tool.name}"
                description = mcp_tool.description or mcp_tool.name

                # Build a Pydantic model from the MCP JSON Schema input schema
                schema = mcp_tool.inputSchema or {}
                fields: Dict[str, Any] = {}
                required_fields = set(schema.get("required", []))
                properties = schema.get("properties", {})

                for prop_name, prop_schema in properties.items():
                    # Map JSON Schema types to Python types
                    json_type = prop_schema.get("type", "string")
                    python_type = self._json_schema_type_to_python(json_type)
                    default = ... if prop_name in required_fields else None
                    fields[prop_name] = (python_type, default)

                DynamicArgs = (
                    create_model(f"{tool_name}Args", **fields)
                    if fields
                    else create_model(f"{tool_name}Args")
                )

                result.append(
                    ToolDefinition(
                        name=tool_name,
                        description=description,
                        args_schema=DynamicArgs,
                        func=_make_tool_func(session, mcp_tool.name),
                    )
                )
        return result

    @staticmethod
    def _json_schema_type_to_python(json_type: str) -> type:
        """Convert JSON Schema type to Python type for Pydantic models."""
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        return type_map.get(json_type, Any)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool by its namespaced name (``mcp__{server_id}__{name}``)."""
        parts = tool_name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool name format: {tool_name!r}")
        server_id, original_name = parts[1], parts[2]
        # Snapshot the connection reference under the lock before awaiting
        async with self._lock:
            connected = self._servers.get(server_id)
        if not connected:
            raise ValueError(f"MCP server '{server_id}' is not connected.")
        result = await connected.session.call_tool(original_name, arguments=arguments)
        return "\n".join(
            c.text if hasattr(c, "text") else str(c) for c in result.content
        )

    async def test_connection(self, server_id: str) -> Dict[str, Any]:
        """Open a fresh connection to verify a server and count its tools."""
        async with self._lock:
            cfg = self._configs.get(server_id)
        if not cfg:
            return {
                "ok": False,
                "error": f"Server '{server_id}' not found in config.",
            }
        connected = await self._connect_server(cfg)
        if not connected:
            return {"ok": False, "error": "Connection attempt failed."}
        tool_names = [t.name for t in connected.tools]
        await connected._exit_stack.aclose()
        return {"ok": True, "tool_count": len(tool_names), "tools": tool_names}

    async def test_connection_with_config(self, cfg: McpServerConfig) -> Dict[str, Any]:
        """Test connection with a McpServerConfig object (for pre-persistence validation).

        Used during add_server to verify connectivity before persisting to mcp_config.json.
        """
        connected = await self._connect_server(cfg)
        if not connected:
            return {"ok": False, "error": "Connection attempt failed."}
        tool_names = [t.name for t in connected.tools]
        await connected._exit_stack.aclose()
        return {"ok": True, "tool_count": len(tool_names), "tools": tool_names}

    def get_server_status(self) -> Dict[str, Any]:
        """Return connection status for every configured server."""
        # Take atomic snapshots so concurrent mutations don't affect iteration
        configs = dict(self._configs)
        servers = dict(self._servers)
        statuses: Dict[str, Any] = {}
        for sid, cfg in configs.items():
            connected = servers.get(sid)
            statuses[sid] = {
                "enabled": cfg.enabled,
                "transport": cfg.transport,
                "connected": connected is not None,
                "tool_count": len(connected.tools) if connected else 0,
            }
        return statuses

    # ------------------------------------------------------------------
    # CRUD operations (persist to mcp_config.json)
    # ------------------------------------------------------------------

    async def add_server_async(self, server_id: str, data: Dict[str, Any]) -> McpServerConfig:
        """Add a new server to the config and persist it (thread-safe)."""
        async with self._lock:
            if server_id in self._configs:
                raise ValueError(f"Server '{server_id}' already exists.")
            cfg = McpServerConfig(server_id, data)
            self._configs[server_id] = cfg
            self._save_config()
            return cfg

    def add_server(self, server_id: str, data: Dict[str, Any]) -> McpServerConfig:
        """Add a new server to the config and persist it. WARNING: Not thread-safe, use add_server_async."""
        # Note: Sync version kept for backward compat with tests, but NOT thread-safe.
        # New code should use add_server_async.
        if server_id in self._configs:
            raise ValueError(f"Server '{server_id}' already exists.")
        cfg = McpServerConfig(server_id, data)
        self._configs[server_id] = cfg
        self._save_config()
        return cfg

    async def update_server_async(
        self, server_id: str, updates: Dict[str, Any]
    ) -> McpServerConfig:
        """Update an existing server config and persist it (thread-safe)."""
        async with self._lock:
            if server_id not in self._configs:
                raise KeyError(f"Server '{server_id}' not found.")
            old = self._configs[server_id]
            merged = old.to_dict()
            merged.update(updates)
            cfg = McpServerConfig(server_id, merged)
            self._configs[server_id] = cfg
            self._save_config()
            return cfg

    def update_server(
        self, server_id: str, updates: Dict[str, Any]
    ) -> McpServerConfig:
        """Update an existing server config and persist it. WARNING: Not thread-safe, use update_server_async."""
        # Note: Sync version kept for backward compat with tests, but NOT thread-safe.
        # New code should use update_server_async.
        if server_id not in self._configs:
            raise KeyError(f"Server '{server_id}' not found.")
        old = self._configs[server_id]
        merged = old.to_dict()
        merged.update(updates)
        cfg = McpServerConfig(server_id, merged)
        self._configs[server_id] = cfg
        self._save_config()
        return cfg

    async def remove_server_async(self, server_id: str) -> None:
        """Remove a server from the config and persist it (thread-safe)."""
        async with self._lock:
            if server_id not in self._configs:
                raise KeyError(f"Server '{server_id}' not found.")
            self._configs.pop(server_id)
            self._save_config()

    def remove_server(self, server_id: str) -> None:
        """Remove a server from the config and persist it. WARNING: Not thread-safe, use remove_server_async."""
        # Note: Sync version kept for backward compat with tests, but NOT thread-safe.
        # New code should use remove_server_async.
        if server_id not in self._configs:
            raise KeyError(f"Server '{server_id}' not found.")
        self._configs.pop(server_id)
        self._save_config()

    # ------------------------------------------------------------------
    # Public lifecycle operations
    # ------------------------------------------------------------------

    async def disconnect_and_remove_server(self, server_id: str) -> None:
        """Disconnect a server and remove it from config (atomic operation)."""
        async with self._lock:
            if server_id not in self._configs:
                raise KeyError(f"Server '{server_id}' not found.")
            await self._disconnect_server(server_id)
            self._configs.pop(server_id)
            self._save_config()

    async def reconnect_server(self, server_id: str) -> Optional[ConnectedServer]:
        """Disconnect then reconnect a single server under the lock."""
        async with self._lock:
            cfg = self._configs.get(server_id)
            if not cfg:
                raise KeyError(f"Server '{server_id}' not found.")
            await self._disconnect_server(server_id)
            if not cfg.enabled:
                return None
            connected = await self._connect_server(cfg)
            if connected:
                self._servers[server_id] = connected
            return connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully disconnect all active MCP servers."""
        async with self._lock:
            for sid in list(self._servers.keys()):
                await self._disconnect_server(sid)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

mcp_manager = McpManager()
