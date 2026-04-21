"""Tests for structured supervisor routing (SupervisorDecision)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from app.core.models import SupervisorDecision
from app.core.agent_graph import AgentGraph, AgentState


# ---------------------------------------------------------------------------
# SupervisorDecision model
# ---------------------------------------------------------------------------

def test_supervisor_decision_respond():
    d = SupervisorDecision(action="respond", response="Hello")
    assert d.action == "respond"
    assert d.response == "Hello"
    assert d.delegate_to is None


def test_supervisor_decision_delegate():
    d = SupervisorDecision(action="delegate", delegate_to="coder")
    assert d.action == "delegate"
    assert d.delegate_to == "coder"


def test_supervisor_decision_use_tool():
    d = SupervisorDecision(action="use_tool")
    assert d.action == "use_tool"


def test_supervisor_decision_parse_valid_json():
    raw = '{"action": "delegate", "delegate_to": "researcher", "reasoning": "needs web"}'
    d = SupervisorDecision.model_validate_json(raw)
    assert d.action == "delegate"
    assert d.delegate_to == "researcher"


def test_supervisor_decision_rejects_unknown_action():
    with pytest.raises(Exception):
        SupervisorDecision(action="unknown_action")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# should_continue routing logic
# ---------------------------------------------------------------------------

def _make_graph():
    llm = MagicMock()
    tools = MagicMock()
    tools.to_openai_tools.return_value = []

    worker_coder = MagicMock()
    worker_coder.role_id = "coder"
    worker_researcher = MagicMock()
    worker_researcher.role_id = "researcher"

    with patch("app.core.agent_graph.role_manager") as mock_rm:
        mock_rm.get_all_workers.return_value = [worker_coder, worker_researcher]
        mock_rm.get_worker.side_effect = lambda rid: worker_coder if rid == "coder" else (
            worker_researcher if rid == "researcher" else None
        )
        graph = AgentGraph(llm, tools)

    return graph


def _state(decision: dict) -> AgentState:
    return {
        "messages": [HumanMessage(content="hi")],
        "next_step": None,
        "tool_calls": None,
        "user_id": "u1",
        "session_id": "s1",
        "current_worker": None,
        "supervisor_decision": decision,
    }


def test_should_continue_respond():
    graph = _make_graph()
    result = graph.should_continue(_state({"action": "respond"}))
    assert result == "end"


def test_should_continue_delegate_coder():
    graph = _make_graph()
    result = graph.should_continue(_state({"action": "delegate", "delegate_to": "coder"}))
    assert result == "worker_coder"


def test_should_continue_delegate_researcher():
    graph = _make_graph()
    result = graph.should_continue(_state({"action": "delegate", "delegate_to": "researcher"}))
    assert result == "worker_researcher"


def test_should_continue_use_tool():
    graph = _make_graph()
    result = graph.should_continue(_state({"action": "use_tool"}))
    assert result == "tools"


def test_should_continue_missing_decision_defaults_end():
    graph = _make_graph()
    result = graph.should_continue(_state({}))
    assert result == "end"


def test_should_continue_delegate_missing_role_id():
    graph = _make_graph()
    result = graph.should_continue(_state({"action": "delegate", "delegate_to": ""}))
    assert result == "end"


# ---------------------------------------------------------------------------
# supervisor_node: JSON parsing and fallback
# ---------------------------------------------------------------------------

def _mock_llm_response(content: str, tool_calls=None):
    """Build a minimal mock that looks like a litellm completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_supervisor_node_parses_delegate_json():
    graph = _make_graph()
    raw = json.dumps({"action": "delegate", "delegate_to": "researcher"})

    with patch.object(graph.llm, "generate", new=AsyncMock(return_value=_mock_llm_response(raw))), \
         patch("app.core.agent_graph.role_manager") as mock_rm, \
         patch("app.core.agent_graph.get_state_manager"), \
         patch("app.core.agent_graph.get_prompt_composer") as mock_pc, \
         patch("app.core.identity.get_identity_manager") as mock_id:

        mock_id.return_value.get_soul.return_value = "soul"
        mock_pc.return_value.compose.return_value = "system"
        mock_rm.get_all_workers.return_value = []
        mock_rm.get_worker.return_value = MagicMock()  # worker exists

        result = await graph.supervisor_node({
            "messages": [HumanMessage(content="search the web")],
            "next_step": None,
            "tool_calls": None,
            "user_id": "u1",
            "session_id": "s1",
            "current_worker": None,
            "supervisor_decision": None,
        })

    assert result["supervisor_decision"]["action"] == "delegate"
    assert result["supervisor_decision"]["delegate_to"] == "researcher"
    assert result["next_step"] == "worker_researcher"


@pytest.mark.asyncio
async def test_supervisor_node_fallback_on_malformed_json():
    graph = _make_graph()

    with patch.object(graph.llm, "generate", new=AsyncMock(return_value=_mock_llm_response("Sure, I can help!"))), \
         patch("app.core.agent_graph.role_manager") as mock_rm, \
         patch("app.core.agent_graph.get_state_manager"), \
         patch("app.core.agent_graph.get_prompt_composer") as mock_pc, \
         patch("app.core.identity.get_identity_manager") as mock_id:

        mock_id.return_value.get_soul.return_value = "soul"
        mock_pc.return_value.compose.return_value = "system"
        mock_rm.get_all_workers.return_value = []

        result = await graph.supervisor_node({
            "messages": [HumanMessage(content="hello")],
            "next_step": None,
            "tool_calls": None,
            "user_id": "u1",
            "session_id": "s1",
            "current_worker": None,
            "supervisor_decision": None,
        })

    assert result["supervisor_decision"]["action"] == "respond"
    assert result["next_step"] == "end"
    # Session must not crash — a message must be present
    assert len(result["messages"]) > 0


@pytest.mark.asyncio
async def test_supervisor_node_native_tool_calls_produce_use_tool():
    graph = _make_graph()
    fake_tc = [{"id": "c1", "function": {"name": "web_search", "arguments": '{"q":"test"}'}}]
    resp = _mock_llm_response("", tool_calls=fake_tc)

    with patch.object(graph.llm, "generate", new=AsyncMock(return_value=resp)), \
         patch("app.core.agent_graph.role_manager") as mock_rm, \
         patch("app.core.agent_graph.get_state_manager"), \
         patch("app.core.agent_graph.get_prompt_composer") as mock_pc, \
         patch("app.core.identity.get_identity_manager") as mock_id:

        mock_id.return_value.get_soul.return_value = "soul"
        mock_pc.return_value.compose.return_value = "system"
        mock_rm.get_all_workers.return_value = []

        result = await graph.supervisor_node({
            "messages": [HumanMessage(content="search")],
            "next_step": None,
            "tool_calls": None,
            "user_id": "u1",
            "session_id": "s1",
            "current_worker": None,
            "supervisor_decision": None,
        })

    assert result["supervisor_decision"]["action"] == "use_tool"
    assert result["next_step"] == "tools"
    assert result["tool_calls"] == fake_tc


@pytest.mark.asyncio
async def test_supervisor_node_all_llm_attempts_fail_no_crash():
    graph = _make_graph()

    with patch.object(graph.llm, "generate", new=AsyncMock(side_effect=RuntimeError("llm down"))), \
         patch.object(graph, "_sleep_async", new=AsyncMock()), \
         patch("app.core.agent_graph.role_manager") as mock_rm, \
         patch("app.core.agent_graph.get_state_manager"), \
         patch("app.core.agent_graph.get_prompt_composer") as mock_pc, \
         patch("app.core.identity.get_identity_manager") as mock_id:

        mock_id.return_value.get_soul.return_value = "soul"
        mock_pc.return_value.compose.return_value = "system"
        mock_rm.get_all_workers.return_value = []

        result = await graph.supervisor_node({
            "messages": [HumanMessage(content="hi")],
            "next_step": None,
            "tool_calls": None,
            "user_id": "u1",
            "session_id": "s1",
            "current_worker": None,
            "supervisor_decision": None,
        })

    assert result["next_step"] == "end"
    assert result["supervisor_decision"]["action"] == "respond"
    assert len(result["messages"]) > 0


@pytest.mark.asyncio
async def test_supervisor_node_retry_drops_response_format():
    """Verify that first attempt uses response_format, but retries drop it for provider fallback."""
    graph = _make_graph()
    call_count = 0
    call_args_list = []

    async def mock_generate(**kwargs):
        nonlocal call_count
        call_count += 1
        # Record the response_format argument from each call
        call_args_list.append(kwargs.get("response_format"))
        # Fail on first attempt to trigger retry
        if call_count == 1:
            raise RuntimeError("provider doesn't support response_format")
        # Succeed on second attempt
        return _mock_llm_response('{"action": "respond", "response": "fallback response"}')

    with patch.object(graph.llm, "generate", new=AsyncMock(side_effect=mock_generate)), \
         patch.object(graph, "_sleep_async", new=AsyncMock()), \
         patch("app.core.agent_graph.role_manager") as mock_rm, \
         patch("app.core.agent_graph.get_state_manager"), \
         patch("app.core.agent_graph.get_prompt_composer") as mock_pc, \
         patch("app.core.identity.get_identity_manager") as mock_id:

        mock_id.return_value.get_soul.return_value = "soul"
        mock_pc.return_value.compose.return_value = "system"
        mock_rm.get_all_workers.return_value = []

        result = await graph.supervisor_node({
            "messages": [HumanMessage(content="test fallback")],
            "next_step": None,
            "tool_calls": None,
            "user_id": "u1",
            "session_id": "s1",
            "current_worker": None,
            "supervisor_decision": None,
        })

    # Verify fallback logic:
    # First call should have response_format=SupervisorDecision
    # Second call should have response_format=None (dropped)
    assert call_count == 2, "Should retry once after first failure"
    assert call_args_list[0] is not None, "First attempt should have response_format"
    assert call_args_list[1] is None, "Retry should have response_format=None (dropped for compatibility)"
    assert result["supervisor_decision"]["action"] == "respond"
    assert result["next_step"] == "end"
