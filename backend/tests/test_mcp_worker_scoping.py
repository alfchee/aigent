"""Tests for per-role MCP tool scoping in the worker nodes of AgentGraph.

Verifies that create_worker_node() passes `mcp_servers=worker_role.mcp_servers`
to ToolRegistry.to_openai_tools(), which prevents cross-role tool leakage.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.agent_graph import AgentGraph, AgentState
from app.core.llm import ModelConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm_response(content: str = "done", tool_calls: list | None = None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_state(text: str = "do something") -> AgentState:
    return {
        "messages": [HumanMessage(content=text)],
        "next_step": None,
        "tool_calls": None,
        "user_id": "u1",
        "session_id": "s1",
        "current_worker": None,
        "supervisor_decision": None,
    }


def _make_worker_role(role_id: str, mcp_servers: List[str]) -> MagicMock:
    role = MagicMock()
    role.role_id = role_id
    role.system_prompt = f"You are {role_id}"
    role.model = "gpt-4o"
    role.mcp_servers = mcp_servers
    role.provider_override = None
    return role


def _make_graph(worker_role: MagicMock) -> AgentGraph:
    llm = MagicMock()
    llm.default_config = ModelConfig(provider="openai", model_name="gpt-4o")
    llm.generate = AsyncMock(return_value=_mock_llm_response())

    tools = MagicMock()
    tools.to_openai_tools = MagicMock(return_value=[])

    with patch("app.core.agent_graph.role_manager") as mock_rm:
        mock_rm.get_all_workers.return_value = [worker_role]
        graph = AgentGraph(llm, tools)

    return graph


# ---------------------------------------------------------------------------
# Per-role mcp_servers passed to to_openai_tools
# ---------------------------------------------------------------------------

class TestWorkerNodeMcpScoping:
    @pytest.mark.asyncio
    async def test_worker_passes_assigned_mcp_servers(self):
        """Worker with mcp_servers=['github', 'fs'] must call to_openai_tools(mcp_servers=[...])."""
        role = _make_worker_role("dev", mcp_servers=["github", "filesystem"])
        graph = _make_graph(role)

        worker_func = graph.create_worker_node(role)
        await worker_func(_make_state())

        graph.tools.to_openai_tools.assert_called_once_with(mcp_servers=["github", "filesystem"])

    @pytest.mark.asyncio
    async def test_worker_passes_empty_list_when_no_mcp_servers(self):
        """Worker with mcp_servers=[] must call to_openai_tools(mcp_servers=[])."""
        role = _make_worker_role("researcher", mcp_servers=[])
        graph = _make_graph(role)

        worker_func = graph.create_worker_node(role)
        await worker_func(_make_state())

        graph.tools.to_openai_tools.assert_called_once_with(mcp_servers=[])

    @pytest.mark.asyncio
    async def test_two_different_workers_pass_different_mcp_servers(self):
        """Different roles pass different server lists; there is no leakage between them."""
        role_a = _make_worker_role("dev", mcp_servers=["github"])
        role_b = _make_worker_role("qa", mcp_servers=["jira"])

        with patch("app.core.agent_graph.role_manager") as mock_rm:
            mock_rm.get_all_workers.return_value = [role_a, role_b]

            llm = MagicMock()
            llm.default_config = ModelConfig(provider="openai", model_name="gpt-4o")
            llm.generate = AsyncMock(return_value=_mock_llm_response())

            tools = MagicMock()
            tools.to_openai_tools = MagicMock(return_value=[])

            graph = AgentGraph(llm, tools)

        worker_a = graph.create_worker_node(role_a)
        worker_b = graph.create_worker_node(role_b)

        await worker_a(_make_state())
        first_call = tools.to_openai_tools.call_args_list[0]
        assert first_call.kwargs["mcp_servers"] == ["github"]

        await worker_b(_make_state())
        second_call = tools.to_openai_tools.call_args_list[1]
        assert second_call.kwargs["mcp_servers"] == ["jira"]

    @pytest.mark.asyncio
    async def test_worker_with_tool_calls_still_uses_scoped_tools(self):
        """Even when the worker produces tool_calls, to_openai_tools is called with mcp_servers."""
        role = _make_worker_role("coder", mcp_servers=["github"])

        fake_tc = MagicMock()
        fake_tc.get = lambda key, default=None: {
            "id": "tc1",
            "function": {"name": "mcp__github__list_prs", "arguments": "{}"},
        }.get(key, default)

        with patch("app.core.agent_graph.role_manager") as mock_rm:
            mock_rm.get_all_workers.return_value = [role]

            llm = MagicMock()
            llm.default_config = ModelConfig(provider="openai", model_name="gpt-4o")
            # LLM returns tool_calls in response
            llm.generate = AsyncMock(return_value=_mock_llm_response(content="", tool_calls=[fake_tc]))

            tools = MagicMock()
            tools.to_openai_tools = MagicMock(return_value=[{"type": "function", "function": {"name": "mcp__github__list_prs"}}])

            graph = AgentGraph(llm, tools)

        worker_func = graph.create_worker_node(role)
        result = await worker_func(_make_state())

        tools.to_openai_tools.assert_called_once_with(mcp_servers=["github"])
        # Worker signals tool execution is needed
        assert result.get("next_step") == "tools"


# ---------------------------------------------------------------------------
# ToolRegistry filtering integration: registry returns correct subset
# ---------------------------------------------------------------------------

class TestRegistryMcpScopingIntegration:
    """Verify that the registry correctly filters tools based on mcp_servers,
    using the real ToolRegistry (not a mock)."""

    def _populate_registry(self):
        from pydantic import create_model
        from app.skills.registry import ToolDefinition, ToolRegistry

        reg = ToolRegistry()
        A = create_model("A")
        B = create_model("B")
        C = create_model("C")
        Skill = create_model("Skill", query=(str, ...))

        reg.register_dynamic(ToolDefinition(name="smart_search", description="s", args_schema=Skill, func=AsyncMock()))
        reg.register_dynamic(ToolDefinition(name="mcp__github__list_prs", description="g", args_schema=A, func=AsyncMock()))
        reg.register_dynamic(ToolDefinition(name="mcp__github__create_issue", description="g2", args_schema=B, func=AsyncMock()))
        reg.register_dynamic(ToolDefinition(name="mcp__jira__get_ticket", description="j", args_schema=C, func=AsyncMock()))
        return reg

    def test_dev_role_gets_only_github_tools(self):
        reg = self._populate_registry()
        tools = reg.to_openai_tools(mcp_servers=["github"])
        names = {t["function"]["name"] for t in tools}
        assert "smart_search" in names
        assert "mcp__github__list_prs" in names
        assert "mcp__github__create_issue" in names
        assert "mcp__jira__get_ticket" not in names

    def test_qa_role_gets_only_jira_tools(self):
        reg = self._populate_registry()
        tools = reg.to_openai_tools(mcp_servers=["jira"])
        names = {t["function"]["name"] for t in tools}
        assert "smart_search" in names
        assert "mcp__jira__get_ticket" in names
        assert "mcp__github__list_prs" not in names

    def test_role_with_no_mcp_gets_only_plain_skills(self):
        reg = self._populate_registry()
        tools = reg.to_openai_tools(mcp_servers=[])
        names = {t["function"]["name"] for t in tools}
        assert "smart_search" in names
        assert not any(n.startswith("mcp__") for n in names)

    def test_supervisor_gets_all_tools(self):
        reg = self._populate_registry()
        tools = reg.to_openai_tools()  # None = no filter = supervisor
        names = {t["function"]["name"] for t in tools}
        assert "smart_search" in names
        assert "mcp__github__list_prs" in names
        assert "mcp__jira__get_ticket" in names
