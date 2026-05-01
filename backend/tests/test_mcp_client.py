"""Unit tests for McpManager (mcp_client.py).

All external MCP connections are mocked — no real servers are required.
"""
from __future__ import annotations

import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import create_model

from app.core.mcp_client import (
    ConnectedServer,
    McpManager,
    McpServerConfig,
    _make_tool_func,
)
from app.skills.registry import ToolDefinition, ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, servers: Dict[str, Any]) -> Path:
    cfg = tmp_path / "mcp_config.json"
    cfg.write_text(json.dumps({"servers": servers}))
    return cfg


def _mock_mcp_tool(name: str, description: str = "", schema: Dict = None):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema or {"properties": {}, "required": []}
    return tool


def _mock_session(tools: list) -> MagicMock:
    session = MagicMock()
    list_result = MagicMock()
    list_result.tools = tools
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=list_result)
    session.call_tool = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# McpServerConfig
# ---------------------------------------------------------------------------

class TestMcpServerConfig:
    def test_stdio_defaults(self):
        cfg = McpServerConfig("gh", {"transport": "stdio", "command": "npx", "args": ["-y", "server-github"]})
        assert cfg.transport == "stdio"
        assert cfg.command == "npx"
        assert cfg.args == ["-y", "server-github"]
        assert cfg.enabled is True

    def test_http_fields(self):
        cfg = McpServerConfig("remote", {"transport": "http", "base_url": "https://example.com", "headers": {"X-Key": "v"}})
        assert cfg.transport == "http"
        assert cfg.base_url == "https://example.com"
        assert cfg.headers == {"X-Key": "v"}

    def test_to_dict_roundtrip(self):
        data = {"transport": "stdio", "command": "node", "args": ["server.js"], "env_vars": {}, "enabled": True}
        cfg = McpServerConfig("s", data)
        assert cfg.to_dict()["command"] == "node"

    def test_to_safe_dict_masks_non_empty_values(self):
        cfg = McpServerConfig("gh", {
            "transport": "stdio",
            "command": "npx",
            "args": [],
            "env_vars": {"GITHUB_TOKEN": "secret123", "EMPTY_VAR": ""},
        })
        safe = cfg.to_safe_dict()
        assert safe["env_vars"]["GITHUB_TOKEN"] == "***"
        assert safe["env_vars"]["EMPTY_VAR"] == ""

    def test_to_safe_dict_masks_http_headers(self):
        cfg = McpServerConfig("remote", {
            "transport": "http",
            "base_url": "https://example.com",
            "headers": {"Authorization": "Bearer tok", "X-Empty": ""},
        })
        safe = cfg.to_safe_dict()
        assert safe["headers"]["Authorization"] == "***"
        assert safe["headers"]["X-Empty"] == ""
        # base_url is not masked
        assert safe["base_url"] == "https://example.com"


# ---------------------------------------------------------------------------
# _make_tool_func
# ---------------------------------------------------------------------------

class TestMakeToolFunc:
    @pytest.mark.asyncio
    async def test_returns_text_content(self):
        content = MagicMock()
        content.text = "hello world"
        call_result = MagicMock()
        call_result.content = [content]

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=call_result)

        func = _make_tool_func(session, "my_tool")
        result = await func(arg1="val1")
        assert result == "hello world"
        session.call_tool.assert_awaited_once_with("my_tool", arguments={"arg1": "val1"})

    @pytest.mark.asyncio
    async def test_empty_args(self):
        content = MagicMock()
        content.text = "ok"
        call_result = MagicMock()
        call_result.content = [content]

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=call_result)

        func = _make_tool_func(session, "no_args_tool")
        result = await func()
        session.call_tool.assert_awaited_once_with("no_args_tool", arguments={})

    @pytest.mark.asyncio
    async def test_concatenates_multiple_content_parts(self):
        c1 = MagicMock()
        c1.text = "part1"
        c2 = MagicMock()
        c2.text = "part2"
        call_result = MagicMock()
        call_result.content = [c1, c2]

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=call_result)

        func = _make_tool_func(session, "multi")
        result = await func()
        assert result == "part1\npart2"


# ---------------------------------------------------------------------------
# McpManager — config loading
# ---------------------------------------------------------------------------

class TestMcpManagerConfig:
    def test_missing_config_returns_empty(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "nonexistent.json")
        configs = mgr._load_config()
        assert configs == {}

    def test_loads_servers(self, tmp_path):
        cfg_path = _write_config(tmp_path, {
            "github": {"transport": "stdio", "command": "npx", "args": [], "enabled": True}
        })
        mgr = McpManager(config_path=cfg_path)
        configs = mgr._load_config()
        assert "github" in configs
        assert configs["github"].transport == "stdio"

    def test_save_and_reload(self, tmp_path):
        cfg_path = _write_config(tmp_path, {})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {"test": McpServerConfig("test", {"transport": "stdio", "command": "echo", "args": [], "env_vars": {}, "enabled": True})}
        mgr._save_config()
        configs = mgr._load_config()
        assert "test" in configs


# ---------------------------------------------------------------------------
# McpManager — CRUD operations
# ---------------------------------------------------------------------------

class TestMcpManagerCrud:
    def test_add_server(self, tmp_path):
        cfg_path = _write_config(tmp_path, {})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {}
        cfg = mgr.add_server("new", {"transport": "stdio", "command": "npx", "args": []})
        assert cfg.server_id == "new"
        assert "new" in mgr._configs
        # Verify it was persisted
        reloaded = mgr._load_config()
        assert "new" in reloaded

    def test_add_server_duplicate_raises(self, tmp_path):
        cfg_path = _write_config(tmp_path, {"existing": {"transport": "stdio", "command": "npx"}})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {"existing": McpServerConfig("existing", {"transport": "stdio", "command": "npx"})}
        with pytest.raises(ValueError, match="already exists"):
            mgr.add_server("existing", {"transport": "stdio"})

    def test_update_server(self, tmp_path):
        cfg_path = _write_config(tmp_path, {})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {"s": McpServerConfig("s", {"transport": "stdio", "command": "old", "args": [], "env_vars": {}})}
        updated = mgr.update_server("s", {"command": "new"})
        assert updated.command == "new"

    def test_update_server_not_found_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {}
        with pytest.raises(KeyError):
            mgr.update_server("ghost", {})

    def test_remove_server(self, tmp_path):
        cfg_path = _write_config(tmp_path, {"s": {"transport": "stdio", "command": "npx"}})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {"s": McpServerConfig("s", {"transport": "stdio", "command": "npx"})}
        mgr.remove_server("s")
        assert "s" not in mgr._configs
        reloaded = mgr._load_config()
        assert "s" not in reloaded

    def test_remove_server_not_found_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {}
        with pytest.raises(KeyError):
            mgr.remove_server("ghost")


# ---------------------------------------------------------------------------
# McpManager — connect / disconnect / get_all_tools
# ---------------------------------------------------------------------------

class TestMcpManagerConnections:
    @pytest.mark.asyncio
    async def test_get_all_tools_empty_when_no_servers(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        tools = await mgr.get_all_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_all_tools_builds_tool_definitions(self, tmp_path):
        mcp_tool = _mock_mcp_tool(
            "search",
            description="Search the web",
            schema={"properties": {"query": {"type": "string"}}, "required": ["query"]},
        )
        mock_session = _mock_session([mcp_tool])
        mock_stack = AsyncExitStack()

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._servers = {
            "myserver": ConnectedServer(
                server_id="myserver",
                session=mock_session,
                tools=[mcp_tool],
                exit_stack=mock_stack,
            )
        }

        tools = await mgr.get_all_tools()
        assert len(tools) == 1
        t = tools[0]
        assert t.name == "mcp__myserver__search"
        assert t.description == "Search the web"
        # Required field → default=...
        fields = t.args_schema.model_fields
        assert "query" in fields

    @pytest.mark.asyncio
    async def test_disconnect_server_removes_entry(self, tmp_path):
        mock_session = _mock_session([])
        stack = MagicMock()
        stack.aclose = AsyncMock()

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._servers = {
            "s1": ConnectedServer("s1", mock_session, [], stack)
        }
        await mgr._disconnect_server("s1")
        assert "s1" not in mgr._servers
        stack.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_servers_skips_disabled(self, tmp_path):
        cfg_path = _write_config(tmp_path, {
            "off": {"transport": "stdio", "command": "npx", "enabled": False}
        })
        mgr = McpManager(config_path=cfg_path)
        await mgr.sync_servers()
        assert "off" not in mgr._servers

    # ------------------------------------------------------------------
    # Validation: empty command / base_url
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_connect_server_skips_stdio_with_empty_command(self, tmp_path):
        """A stdio server with an empty command is skipped (no exception, no connection)."""
        cfg = McpServerConfig("stub", {"transport": "stdio", "command": "", "enabled": True})
        mgr = McpManager(config_path=tmp_path / "x.json")
        result = await mgr._connect_server(cfg)
        assert result is None

    @pytest.mark.asyncio
    async def test_connect_server_skips_stdio_with_whitespace_command(self, tmp_path):
        """A stdio server with a whitespace-only command is also skipped."""
        cfg = McpServerConfig("stub", {"transport": "stdio", "command": "   ", "enabled": True})
        mgr = McpManager(config_path=tmp_path / "x.json")
        result = await mgr._connect_server(cfg)
        assert result is None

    @pytest.mark.asyncio
    async def test_connect_server_skips_http_with_empty_base_url(self, tmp_path):
        """An http server with an empty base_url is skipped."""
        cfg = McpServerConfig("stub", {"transport": "http", "base_url": "", "enabled": True})
        mgr = McpManager(config_path=tmp_path / "x.json")
        result = await mgr._connect_server(cfg)
        assert result is None

    @pytest.mark.asyncio
    async def test_connect_server_skips_sse_with_empty_base_url(self, tmp_path):
        """An sse server with an empty base_url is skipped."""
        cfg = McpServerConfig("stub", {"transport": "sse", "base_url": "  ", "enabled": True})
        mgr = McpManager(config_path=tmp_path / "x.json")
        result = await mgr._connect_server(cfg)
        assert result is None

    @pytest.mark.asyncio
    async def test_sync_servers_skips_enabled_stdio_with_empty_command(self, tmp_path):
        """sync_servers does not connect an enabled stdio server that has no command."""
        cfg_path = _write_config(tmp_path, {
            "stub": {"transport": "stdio", "command": "", "enabled": True}
        })
        mgr = McpManager(config_path=cfg_path)
        await mgr.sync_servers()
        assert "stub" not in mgr._servers

    @pytest.mark.asyncio
    async def test_call_tool_dispatches_to_session(self, tmp_path):
        content = MagicMock()
        content.text = "result"
        call_result = MagicMock()
        call_result.content = [content]
        mock_session = MagicMock()
        mock_session.call_tool = AsyncMock(return_value=call_result)

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._servers = {
            "srv": ConnectedServer("srv", mock_session, [], AsyncExitStack())
        }
        out = await mgr.call_tool("mcp__srv__do_thing", {"x": 1})
        assert out == "result"
        mock_session.call_tool.assert_awaited_once_with("do_thing", arguments={"x": 1})

    @pytest.mark.asyncio
    async def test_call_tool_invalid_name_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        with pytest.raises(ValueError, match="Invalid MCP tool name"):
            await mgr.call_tool("bad_name", {})

    @pytest.mark.asyncio
    async def test_call_tool_disconnected_server_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._servers = {}
        with pytest.raises(ValueError, match="not connected"):
            await mgr.call_tool("mcp__ghost__tool", {})

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_all(self, tmp_path):
        s1 = MagicMock()
        s1.aclose = AsyncMock()
        s2 = MagicMock()
        s2.aclose = AsyncMock()

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._servers = {
            "a": ConnectedServer("a", MagicMock(), [], s1),
            "b": ConnectedServer("b", MagicMock(), [], s2),
        }
        await mgr.shutdown()
        assert mgr._servers == {}
        s1.aclose.assert_awaited_once()
        s2.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconnect_server_disconnects_then_reconnects(self, tmp_path):
        old_stack = MagicMock()
        old_stack.aclose = AsyncMock()
        new_connected = ConnectedServer("srv", MagicMock(), [_mock_mcp_tool("t")], AsyncExitStack())

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {"srv": McpServerConfig("srv", {"transport": "stdio", "command": "npx", "enabled": True})}
        mgr._servers = {"srv": ConnectedServer("srv", MagicMock(), [], old_stack)}

        # Patch _connect_server to return a new connection
        async def _fake_connect(cfg):
            return new_connected

        mgr._connect_server = _fake_connect
        result = await mgr.reconnect_server("srv")

        old_stack.aclose.assert_awaited_once()
        assert mgr._servers["srv"] is new_connected
        assert result is new_connected

    @pytest.mark.asyncio
    async def test_reconnect_server_unknown_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {}
        with pytest.raises(KeyError, match="not found"):
            await mgr.reconnect_server("ghost")

    @pytest.mark.asyncio
    async def test_reconnect_server_disabled_does_not_reconnect(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {"off": McpServerConfig("off", {"transport": "stdio", "command": "x", "enabled": False})}
        mgr._servers = {}
        result = await mgr.reconnect_server("off")
        assert result is None
        assert "off" not in mgr._servers

    @pytest.mark.asyncio
    async def test_sync_servers_connects_new_enabled(self, tmp_path):
        new_connected = ConnectedServer("srv", MagicMock(), [_mock_mcp_tool("t")], AsyncExitStack())
        cfg_path = _write_config(tmp_path, {
            "srv": {"transport": "stdio", "command": "npx", "enabled": True}
        })
        mgr = McpManager(config_path=cfg_path)

        async def _fake_connect(cfg):
            return new_connected

        mgr._connect_server = _fake_connect
        await mgr.sync_servers()
        assert "srv" in mgr._servers
        assert mgr._servers["srv"] is new_connected

    @pytest.mark.asyncio
    async def test_sync_servers_disconnects_removed_server(self, tmp_path):
        old_stack = MagicMock()
        old_stack.aclose = AsyncMock()
        cfg_path = _write_config(tmp_path, {})  # empty config
        mgr = McpManager(config_path=cfg_path)
        # Server was connected but no longer in config
        mgr._servers = {"old_srv": ConnectedServer("old_srv", MagicMock(), [], old_stack)}
        await mgr.sync_servers()
        assert "old_srv" not in mgr._servers
        old_stack.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_servers_disconnects_disabled_server(self, tmp_path):
        old_stack = MagicMock()
        old_stack.aclose = AsyncMock()
        cfg_path = _write_config(tmp_path, {
            "srv": {"transport": "stdio", "command": "x", "enabled": False}
        })
        mgr = McpManager(config_path=cfg_path)
        # Server is connected but config now has it disabled
        mgr._servers = {"srv": ConnectedServer("srv", MagicMock(), [], old_stack)}
        await mgr.sync_servers()
        assert "srv" not in mgr._servers
        old_stack.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# McpManager — test_connection
# ---------------------------------------------------------------------------

class TestMcpManagerTestConnection:
    @pytest.mark.asyncio
    async def test_test_connection_success(self, tmp_path):
        tool = _mock_mcp_tool("my_tool")
        mock_exit = MagicMock()
        mock_exit.aclose = AsyncMock()
        new_connected = ConnectedServer("srv", MagicMock(), [tool], mock_exit)

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {"srv": McpServerConfig("srv", {"transport": "stdio", "command": "x"})}

        async def _fake_connect(cfg):
            return new_connected

        mgr._connect_server = _fake_connect
        result = await mgr.test_connection("srv")

        assert result["ok"] is True
        assert result["tool_count"] == 1
        assert "my_tool" in result["tools"]
        # The temporary connection is closed after the test
        mock_exit.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_connection_server_not_in_config(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {}
        result = await mgr.test_connection("ghost")
        assert result["ok"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_test_connection_connect_fails(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {"srv": McpServerConfig("srv", {"transport": "stdio", "command": "x"})}

        async def _fake_connect(cfg):
            return None  # Connection failed

        mgr._connect_server = _fake_connect
        result = await mgr.test_connection("srv")
        assert result["ok"] is False
        assert "Connection attempt failed" in result["error"]


# ---------------------------------------------------------------------------
# McpManager — disconnect_and_remove_server
# ---------------------------------------------------------------------------

class TestMcpManagerDisconnectAndRemove:
    @pytest.mark.asyncio
    async def test_disconnect_and_remove_success(self, tmp_path):
        stack = MagicMock()
        stack.aclose = AsyncMock()
        cfg_path = _write_config(tmp_path, {"srv": {"transport": "stdio", "command": "x"}})
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {"srv": McpServerConfig("srv", {"transport": "stdio", "command": "x"})}
        mgr._servers = {"srv": ConnectedServer("srv", MagicMock(), [], stack)}

        await mgr.disconnect_and_remove_server("srv")

        assert "srv" not in mgr._servers
        assert "srv" not in mgr._configs
        stack.aclose.assert_awaited_once()
        # Verify persisted
        reloaded = mgr._load_config()
        assert "srv" not in reloaded

    @pytest.mark.asyncio
    async def test_disconnect_and_remove_not_found_raises(self, tmp_path):
        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {}
        with pytest.raises(KeyError, match="not found"):
            await mgr.disconnect_and_remove_server("ghost")

    @pytest.mark.asyncio
    async def test_disconnect_and_remove_leaves_other_servers_untouched(self, tmp_path):
        cfg_path = _write_config(tmp_path, {
            "a": {"transport": "stdio", "command": "x"},
            "b": {"transport": "stdio", "command": "y"},
        })
        stack_a = MagicMock()
        stack_a.aclose = AsyncMock()
        mgr = McpManager(config_path=cfg_path)
        mgr._configs = {
            "a": McpServerConfig("a", {"transport": "stdio", "command": "x"}),
            "b": McpServerConfig("b", {"transport": "stdio", "command": "y"}),
        }
        mgr._servers = {
            "a": ConnectedServer("a", MagicMock(), [], stack_a),
        }
        await mgr.disconnect_and_remove_server("a")
        assert "b" in mgr._configs


# ---------------------------------------------------------------------------
# McpManager — get_server_status
# ---------------------------------------------------------------------------

class TestMcpManagerStatus:
    def test_status_reflects_connection_state(self, tmp_path):
        mcp_tool = _mock_mcp_tool("t1")
        mock_session = MagicMock()

        mgr = McpManager(config_path=tmp_path / "x.json")
        mgr._configs = {
            "connected_srv": McpServerConfig("connected_srv", {"transport": "stdio", "command": "x", "enabled": True}),
            "disconnected_srv": McpServerConfig("disconnected_srv", {"transport": "http", "base_url": "http://x.com", "enabled": True}),
        }
        mgr._servers = {
            "connected_srv": ConnectedServer("connected_srv", mock_session, [mcp_tool], AsyncExitStack())
        }
        status = mgr.get_server_status()
        assert status["connected_srv"]["connected"] is True
        assert status["connected_srv"]["tool_count"] == 1
        assert status["disconnected_srv"]["connected"] is False
        assert status["disconnected_srv"]["tool_count"] == 0


# ---------------------------------------------------------------------------
# ToolRegistry — register_dynamic and MCP filtering
# ---------------------------------------------------------------------------

class TestToolRegistryMcpFiltering:
    def _make_registry_with_tools(self) -> ToolRegistry:
        reg = ToolRegistry()
        # A plain (non-MCP) skill
        SkillArgs = create_model("SkillArgs", query=(str, ...))
        reg.register_dynamic(ToolDefinition(
            name="smart_search",
            description="Search",
            args_schema=SkillArgs,
            func=AsyncMock(),
        ))
        # MCP tool for server "s1"
        S1Args = create_model("S1Args")
        reg.register_dynamic(ToolDefinition(
            name="mcp__s1__tool_a",
            description="Tool A on s1",
            args_schema=S1Args,
            func=AsyncMock(),
        ))
        # MCP tool for server "s2"
        S2Args = create_model("S2Args")
        reg.register_dynamic(ToolDefinition(
            name="mcp__s2__tool_b",
            description="Tool B on s2",
            args_schema=S2Args,
            func=AsyncMock(),
        ))
        return reg

    def test_no_filter_returns_all(self):
        reg = self._make_registry_with_tools()
        tools = reg.to_openai_tools()
        names = [t["function"]["name"] for t in tools]
        assert "smart_search" in names
        assert "mcp__s1__tool_a" in names
        assert "mcp__s2__tool_b" in names

    def test_empty_mcp_servers_excludes_mcp_tools(self):
        reg = self._make_registry_with_tools()
        tools = reg.to_openai_tools(mcp_servers=[])
        names = [t["function"]["name"] for t in tools]
        assert "smart_search" in names
        assert "mcp__s1__tool_a" not in names
        assert "mcp__s2__tool_b" not in names

    def test_specific_mcp_servers_filters_correctly(self):
        reg = self._make_registry_with_tools()
        tools = reg.to_openai_tools(mcp_servers=["s1"])
        names = [t["function"]["name"] for t in tools]
        assert "smart_search" in names
        assert "mcp__s1__tool_a" in names
        assert "mcp__s2__tool_b" not in names

    def test_malformed_mcp_name_rejected_at_registration(self):
        """Malformed MCP tool names (only 2 parts) are rejected at registration time."""
        reg = ToolRegistry()
        MalArgs = create_model("MalArgs")
        with pytest.raises(ValueError, match="Malformed MCP tool name"):
            reg.register_dynamic(ToolDefinition(
                name="mcp__s1",  # missing the third segment
                description="malformed",
                args_schema=MalArgs,
                func=AsyncMock(),
            ))

    def test_non_mcp_tool_can_have_any_name(self):
        """Non-MCP tools (not starting with 'mcp__') can have any name."""
        reg = ToolRegistry()
        AnyArgs = create_model("AnyArgs")
        # This should NOT raise, even though it starts with "mcp" but doesn't follow mcp__ pattern
        reg.register_dynamic(ToolDefinition(
            name="mcp_utils_helper",  # doesn't start with "mcp__" so no validation
            description="helper",
            args_schema=AnyArgs,
            func=AsyncMock(),
        ))
        assert reg.get_tool("mcp_utils_helper") is not None

    def test_register_dynamic_stores_tool(self):
        reg = ToolRegistry()
        DynArgs = create_model("DynArgs")
        td = ToolDefinition(name="dyn", description="d", args_schema=DynArgs, func=AsyncMock())
        reg.register_dynamic(td)
        assert reg.get_tool("dyn") is td

    @pytest.mark.asyncio
    async def test_remove_tools_by_prefix(self):
        reg = ToolRegistry()
        # Add some tools
        DynArgs = create_model("DynArgs")
        reg.register_dynamic(ToolDefinition(name="mcp__s1__tool1", description="t1", args_schema=DynArgs, func=AsyncMock()))
        reg.register_dynamic(ToolDefinition(name="mcp__s1__tool2", description="t2", args_schema=DynArgs, func=AsyncMock()))
        reg.register_dynamic(ToolDefinition(name="mcp__s2__tool3", description="t3", args_schema=DynArgs, func=AsyncMock()))
        # Remove by prefix
        removed = reg.remove_tools_by_prefix("mcp__s1__")
        assert set(removed) == {"mcp__s1__tool1", "mcp__s1__tool2"}
        assert reg.get_tool("mcp__s2__tool3") is not None
        assert reg.get_tool("mcp__s1__tool1") is None

    @pytest.mark.asyncio
    async def test_end_to_end_mcp_tool_execution(self):
        """Test executing an MCP tool through the registry.execute() path."""
        # Create a mock MCP tool
        async def mock_tool_impl(query: str) -> str:
            return f"Result for {query}"

        args_schema = create_model("SearchArgs", query=(str, ...))
        tool_def = ToolDefinition(
            name="mcp__test_srv__search",
            description="Search tool",
            args_schema=args_schema,
            func=mock_tool_impl,
        )

        # Register it
        reg = ToolRegistry()
        reg.register_dynamic(tool_def)

        # Execute through the registry
        result = await reg.execute("mcp__test_srv__search", {"query": "hello"})
        assert result == "Result for hello"

    @pytest.mark.asyncio
    async def test_mcp_tools_filter_by_server(self):
        """Test that mcp_servers parameter correctly filters tools."""
        reg = ToolRegistry()

        # Add a non-MCP tool
        PlainArgs = create_model("PlainArgs")
        reg.register_dynamic(ToolDefinition(
            name="plain_tool",
            description="Plain tool",
            args_schema=PlainArgs,
            func=AsyncMock(),
        ))

        # Add MCP tools from different servers
        MCP1Args = create_model("MCP1Args")
        reg.register_dynamic(ToolDefinition(
            name="mcp__server1__tool_a",
            description="Tool A",
            args_schema=MCP1Args,
            func=AsyncMock(),
        ))

        MCP2Args = create_model("MCP2Args")
        reg.register_dynamic(ToolDefinition(
            name="mcp__server2__tool_b",
            description="Tool B",
            args_schema=MCP2Args,
            func=AsyncMock(),
        ))

        # Get all tools
        all_tools = reg.to_openai_tools()
        assert len(all_tools) == 3

        # Filter to only server1
        filtered = reg.to_openai_tools(mcp_servers=["server1"])
        names = [t["function"]["name"] for t in filtered]
        assert "plain_tool" in names
        assert "mcp__server1__tool_a" in names
        assert "mcp__server2__tool_b" not in names
