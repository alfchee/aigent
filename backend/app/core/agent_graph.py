from typing import Annotated, Dict, List, Optional, TypedDict, Any
import asyncio
import json
import logging
import os
import re
import threading
import time
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, FunctionMessage, ToolMessage
from app.core.llm import LLMService, ModelConfig, default_llm
from app.core.models import SupervisorDecision
from app.core.state_manager import get_state_manager
from app.core.prompt_composer import get_prompt_composer
from app.core.refiner import RefinerNode
from app.skills.registry import ToolRegistry, registry
from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox
from app.core.chat_persistence import ChatPersistence
from app.core.roles import role_manager

logger = logging.getLogger("navibot.agent_graph")

# Store full LangChain message history per session
SESSION_HISTORIES: Dict[str, List[BaseMessage]] = {}

# Persistence backend for session histories
_chat_persistence = ChatPersistence()

# Last-access timestamps (monotonic) used for in-memory TTL eviction
# NOTE: This TTL tracking is per-process only. In multi-process deployments (gunicorn, etc.),
# each worker maintains its own access time tracking, leading to inconsistent memory usage
# across workers. Consider implementing a shared cache layer or distributed session storage
# for production deployments with multiple workers.
_SESSION_LAST_ACCESS: Dict[str, float] = {}
_SESSION_TTL_DAYS: int = int(os.getenv("SESSION_TTL_DAYS", "7"))

# Per-session locks to prevent concurrent modifications within a single process
_SESSION_LOCKS: Dict[str, threading.RLock] = {}
_SESSION_LOCKS_MANAGER = threading.Lock()

# Tracks the most-recently delegated role_id per session (used for DELETE guard)
_session_active_roles: Dict[str, str] = {}
_session_active_roles_lock = threading.Lock()


def get_sessions_using_role(role_id: str) -> List[str]:
    """Return session IDs whose last delegated role matches *role_id*."""
    with _session_active_roles_lock:
        return [sid for sid, rid in _session_active_roles.items() if rid == role_id]


def _get_session_lock(session_id: str) -> threading.RLock:
    """Get or create a lock for the given session."""
    with _SESSION_LOCKS_MANAGER:
        if session_id not in _SESSION_LOCKS:
            _SESSION_LOCKS[session_id] = threading.RLock()
        return _SESSION_LOCKS[session_id]


def _evict_stale_sessions() -> None:
    """Remove in-memory entries for sessions inactive longer than SESSION_TTL_DAYS."""
    ttl_seconds = _SESSION_TTL_DAYS * 86_400
    now = time.monotonic()
    stale = [
        sid
        for sid, last_access in list(_SESSION_LAST_ACCESS.items())
        if (now - last_access) > ttl_seconds
    ]
    for sid in stale:
        SESSION_HISTORIES.pop(sid, None)
        _SESSION_LAST_ACCESS.pop(sid, None)
        with _session_active_roles_lock:
            _session_active_roles.pop(sid, None)
        logger.debug("Evicted stale in-memory session: %s", sid)


def _sanitize_for_logging(text: str, max_len: int = 200) -> str:
    """Sanitize text for logging by redacting potential PII and truncating."""
    # Redact email addresses
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[email]', text)
    # Redact phone numbers (basic pattern)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone]', text)
    # Redact API keys / tokens (common patterns)
    text = re.sub(r'(api[_-]?key|token|secret)["\']?\s*[:=]\s*["\']?[\w-]+', '[credential]', text)
    return text[:max_len]


# Error messages for supervisor fallbacks (keep consistent across all paths)
ERROR_INCONCLUSIVE = "No encontré una respuesta concluyente en este intento. Intenta reformular o especificar la fuente."
ERROR_WORKER_NOT_FOUND = "No se pudo encontrar el especialista solicitado."
ERROR_TOOL_EXECUTION = "No se pudo ejecutar la herramienta solicitada."


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next_step: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    user_id: Optional[str]
    session_id: Optional[str]
    current_worker: Optional[str]
    # supervisor_decision is stored as Dict[str, Any] (not SupervisorDecision directly)
    # to avoid LangGraph serialization issues with Pydantic models.
    # Reconstructed on access in should_continue().
    supervisor_decision: Optional[Dict[str, Any]]


def _format_messages_for_llm(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """
    Converts LangChain messages to the format expected by LiteLM.
    Handles Gemini's strict function-call protocol:
      - Function results must be a user turn immediately following the AI tool_calls turn.
      - Content must be a JSON string with {tool_call_id, name, content}.
    Safety: always ends with a user-turn message (required by Gemini).
    """
    formatted: List[Dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append({"role": "user", "content": msg.content or ""})

        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tc_id = tc.get("id") or tc.get("tool_call_id") or ""
                    fn_name = tc.get("name") or ""
                    args_raw = tc.get("arguments") or {}
                    if isinstance(args_raw, str):
                        try:
                            json.loads(args_raw)
                            args_str = args_raw
                        except json.JSONDecodeError:
                            args_str = "{}"
                    else:
                        args_str = json.dumps(args_raw)
                    formatted.append({
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tc_id,
                                "type": "function",
                                "function": {"name": fn_name, "arguments": args_str},
                            }
                        ],
                    })
            elif msg.content:
                formatted.append({"role": "assistant", "content": msg.content})

        elif isinstance(msg, ToolMessage):
            formatted.append({
                "role": "user",
                "content": json.dumps({
                    "tool_call_id": getattr(msg, "tool_call_id", "") or "",
                    "name": getattr(msg, "name", "") or "",
                    "content": msg.content or "",
                }),
            })

        elif isinstance(msg, FunctionMessage):
            formatted.append({
                "role": "user",
                "content": json.dumps({
                    "tool_call_id": getattr(msg, "tool_call_id", "") or "",
                    "name": getattr(msg, "name", "") or "",
                    "content": msg.content or "",
                }),
            })

    # Gemini enforce: single-turn requests must end with role=user.
    # If the last message is role=assistant without tool_calls, inject a sentinel.
    if formatted and formatted[-1].get("role") == "assistant":
        last_has_tool_call = bool(formatted[-1].get("tool_calls"))
        if not last_has_tool_call:
            logger.warning(
                "_format_messages_for_llm: last message is assistant without tool_call. "
                "Appending sentinel. Sequence roles: %s",
                [m.get("role") for m in formatted],
            )
            formatted.append({"role": "user", "content": "(continue)"})

    return formatted


class AgentGraph:
    def __init__(self, llm_service: LLMService, tool_registry: ToolRegistry):
        self.llm = llm_service
        self.tools = tool_registry
        self.workflow = StateGraph(AgentState)
        self._build_graph()
        self.refiner = RefinerNode(llm_service)

    def get_memory_controller(self, user_id: str) -> MemoryController:
        return MemoryController(user_id=user_id)

    def _build_graph(self):
        self.workflow.add_node("supervisor", self.supervisor_node)
        self.workflow.add_node("tools", self.tools_node)

        workers = role_manager.get_all_workers()
        for worker in workers:
            self.workflow.add_node(
                f"worker_{worker.role_id}",
                self.create_worker_node(worker),
            )

        self.workflow.set_entry_point("supervisor")

        self.workflow.add_conditional_edges(
            "supervisor",
            self.should_continue,
            {
                "tools": "tools",
                "end": END,
                **{f"worker_{w.role_id}": f"worker_{w.role_id}" for w in workers},
            },
        )

        for worker in workers:
            self.workflow.add_edge(f"worker_{worker.role_id}", "supervisor")
        self.workflow.add_edge("tools", "supervisor")

        self.app = self.workflow.compile()

    def create_worker_node(self, worker_role):
        async def worker_func(state: AgentState) -> Dict[str, Any]:
            messages = state["messages"]
            worker_messages: List[Dict[str, Any]] = [
                {"role": "system", "content": worker_role.system_prompt}
            ]
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    worker_messages.append({"role": "user", "content": msg.content or ""})
                elif isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            tc_id = tc.get("id") or ""
                            fn_name = tc.get("name") or ""
                            args_str = json.dumps(tc.get("arguments") or {})
                            worker_messages.append({
                                "role": "assistant",
                                "tool_calls": [{
                                    "id": tc_id,
                                    "type": "function",
                                    "function": {"name": fn_name, "arguments": args_str},
                                }],
                            })
                    elif msg.content:
                        worker_messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, ToolMessage):
                    worker_messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "tool_call_id": getattr(msg, "tool_call_id", "") or "",
                            "name": getattr(msg, "name", "") or "",
                            "content": msg.content or "",
                        }),
                    })

            worker_config = ModelConfig(
                provider=worker_role.provider_override or self.llm.default_config.provider,
                model_name=worker_role.model,
                temperature=self.llm.default_config.temperature,
                max_tokens=self.llm.default_config.max_tokens,
                api_key=self.llm.get_api_key(worker_role.provider_override) if worker_role.provider_override else self.llm.default_config.api_key,
                base_url=self.llm.get_base_url(worker_role.provider_override) if worker_role.provider_override else self.llm.default_config.base_url,
            )
            # Filter MCP tools to only those assigned to this role
            available_tools = self.tools.to_openai_tools(
                mcp_servers=worker_role.mcp_servers
            )
            response = await self.llm.generate(
                messages=worker_messages,
                config=worker_config,
                tools=available_tools if available_tools else None,
            )
            choice = response.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None) or []
            content = choice.content or ""

            new_messages: List[BaseMessage] = []

            if tool_calls:
                tc_msg = AIMessage(content="")
                tc_msg.tool_calls = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "name": tc.get("function", {}).get("name", "unknown"),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    }
                    for i, tc in enumerate(tool_calls)
                ]
                new_messages.append(tc_msg)
                return {
                    "messages": new_messages,
                    "tool_calls": tool_calls,
                    "next_step": "tools",
                }
            elif content:
                new_messages.append(AIMessage(content=content))
            else:
                new_messages.append(
                    AIMessage(
                        content="No pude completar la investigación en este intento. Intenta reformular la consulta."
                    )
                )

            return {"messages": new_messages, "tool_calls": None, "next_step": "end"}

        return worker_func

    async def supervisor_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Supervisor decides next action: delegate, use a tool, or respond directly.
        Implements graceful error recovery with retry and graceful degradation.
        """
        messages = state["messages"]
        available_tools = self.tools.to_openai_tools()
        user_id = state.get("user_id", "default_user")
        memory = self.get_memory_controller(user_id)

        last_message_text = ""
        if messages:
            last = messages[-1]
            if isinstance(last, HumanMessage):
                last_message_text = last.content or ""
            elif isinstance(last, ToolMessage):
                last_message_text = last.content or ""

        semantic_context = memory.retrieve_context(last_message_text) if last_message_text else ""

        state_mgr = get_state_manager()
        dashboard = state_mgr.get_dashboard(session_id=state.get("session_id", ""))

        from app.core.identity import get_identity_manager
        soul_prompt = get_identity_manager().get_soul()

        base_prompt = f"""{soul_prompt}

## Global State Dashboard
{dashboard}

## Memory Context
{semantic_context if semantic_context else '(no memory context)'}

## Available Workers
{json.dumps([w.dict() for w in role_manager.get_all_workers()], indent=2)}

Analyze the user's request and respond with a JSON object.

### Valid Examples:

For delegation:
{{"action": "delegate", "delegate_to": "researcher", "reasoning": "needs web search"}}

For direct response:
{{"action": "respond", "response": "Here is the answer..."}}

For tool use:
{{"action": "use_tool", "reasoning": "fetching data"}}

### Rules:
- action must be exactly one of: "delegate", "respond", or "use_tool"
- Only include delegate_to if action is "delegate"
- Only include response if action is "respond"
- Never use "DELEGATE:" text format
- Always return valid JSON"""

        composer = get_prompt_composer()
        system_prompt = composer.compose(
            base_prompt=base_prompt,
            user_message=last_message_text,
            context={"session_id": state.get("session_id", "")},
        )

        litellm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        formatted = _format_messages_for_llm(messages)
        litellm_messages.extend(formatted)

        logger.debug(
            "supervisor_node: session=%s message_roles=%s",
            state.get("session_id"),
            [m.get("role") for m in litellm_messages],
        )

        response = None
        last_error = ""
        for attempt in range(3):
            try:
                # First attempt uses structured output; subsequent retries fall back to plain text
                # so providers that reject response_format still succeed.
                fmt = SupervisorDecision if attempt == 0 else None
                response = await self.llm.generate(
                    messages=litellm_messages,
                    response_format=fmt,
                    tools=available_tools if available_tools else None,
                )
                break
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Supervisor LLM attempt %s/3 failed for session %s: %s",
                    attempt + 1,
                    state.get("session_id", ""),
                    last_error,
                )
                if attempt < 2:
                    await self._sleep_async(2 ** attempt * 0.5)

        if response is None:
            logger.error("All LLM attempts failed for supervisor, returning error response")
            return {
                "messages": [AIMessage(content=f"I encountered an error processing your request. Please try again. ({last_error[:100]})")],
                "tool_calls": None,
                "next_step": "end",
                "supervisor_decision": {"action": "respond"},
            }

        choice = response.choices[0].message
        content: str = choice.content or ""
        tool_calls = getattr(choice, "tool_calls", None) or []

        new_messages: List[BaseMessage] = []
        next_step = "end"
        supervisor_decision: Dict[str, Any] = {"action": "respond"}

        if tool_calls:
            # Native tool calls — already structured, treat as use_tool
            supervisor_decision = {"action": "use_tool"}
            next_step = "tools"
            tc_msg = AIMessage(content="")
            tc_msg.tool_calls = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "name": tc.get("function", {}).get("name", "unknown"),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                }
                for i, tc in enumerate(tool_calls)
            ]
            new_messages.append(tc_msg)
        else:
            # Parse structured decision; fall back gracefully on any parse error
            decision: Optional[SupervisorDecision] = None
            if content:
                try:
                    decision = SupervisorDecision.model_validate_json(content)
                except Exception:
                    try:
                        decision = SupervisorDecision.model_validate(json.loads(content))
                    except Exception:
                        logger.warning(
                            "supervisor_node: could not parse SupervisorDecision for session %s, "
                            "falling back to respond. content=%r",
                            state.get("session_id", ""),
                            _sanitize_for_logging(content),
                        )
                        decision = SupervisorDecision(action="respond", response=content)

            if decision is None:
                decision = SupervisorDecision(action="respond", response=ERROR_INCONCLUSIVE)

            supervisor_decision = decision.model_dump()

            if decision.action == "delegate":
                role_id = decision.delegate_to or ""
                if role_id and role_manager.get_worker(role_id):
                    next_step = f"worker_{role_id}"
                    _sid = state.get("session_id") or ""
                    if _sid:
                        with _session_active_roles_lock:
                            _session_active_roles[_sid] = role_id
                else:
                    logger.warning(
                        "supervisor_node: delegate_to=%r not found, falling back to respond", role_id
                    )
                    supervisor_decision = {"action": "respond"}
                    new_messages.append(AIMessage(content=decision.response or ERROR_WORKER_NOT_FOUND))
            elif decision.action == "respond":
                new_messages.append(AIMessage(content=decision.response or ERROR_INCONCLUSIVE))
            else:
                # action="use_tool" without native tool_calls — edge case that should rarely occur.
                # Normally when the LLM wants to use a tool, it returns native tool_calls (handled above).
                # This case means the JSON structured output indicated tool use but the LLM didn't
                # provide the actual tool call details. Treat as a respond fallback.
                logger.warning(
                    "supervisor_node: action=use_tool but no tool_calls in response for session %s",
                    state.get("session_id", ""),
                )
                new_messages.append(AIMessage(content=decision.response or ERROR_TOOL_EXECUTION))

        return {
            "messages": new_messages,
            "tool_calls": tool_calls,
            "next_step": next_step,
            "supervisor_decision": supervisor_decision,
        }

    async def tools_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes requested tools and returns results as ToolMessages.
        Each result becomes a user turn for Gemini (function_response format).
        """
        tool_calls = state.get("tool_calls") or []
        results: List[BaseMessage] = []

        for call in tool_calls:
            function_name = call.get("name") or call.get("function", {}).get("name", "")
            raw_args = call.get("arguments") or call.get("function", {}).get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            else:
                arguments = raw_args

            tool_call_id = call.get("id", "")

            try:
                output = await self.tools.execute(function_name, arguments)
                results.append(
                    ToolMessage(content=str(output), tool_call_id=tool_call_id, name=function_name)
                )
                logger.info(
                    "tools_node: executed tool=%s call_id=%s output_len=%s",
                    function_name,
                    tool_call_id,
                    len(str(output)),
                )
            except Exception as exc:
                logger.exception("Tool '%s' failed during execution", function_name)
                results.append(
                    ToolMessage(
                        content=f"Error executing {function_name}: {str(exc)}",
                        tool_call_id=tool_call_id,
                        name=function_name,
                    )
                )

        return {"messages": results, "tool_calls": None}

    def should_continue(self, state: AgentState) -> str:
        decision = state.get("supervisor_decision") or {}
        action = decision.get("action", "respond")
        if action == "delegate":
            role_id = decision.get("delegate_to", "")
            return f"worker_{role_id}" if role_id else "end"
        if action == "use_tool":
            return "tools"
        return "end"

    async def _sleep_async(self, seconds: float):
        import asyncio
        await asyncio.sleep(seconds)

    async def run_turn(self, user_text: str, user_id: str, session_id: str) -> str:
        global SESSION_HISTORIES, _SESSION_LAST_ACCESS

        # Get per-session lock to prevent concurrent load/modify/save race conditions
        session_lock = _get_session_lock(session_id)

        # Acquire lock before loading and modifying history
        def _load_history_locked():
            with session_lock:
                # Load history from SQLite on first access within this process lifetime
                if session_id not in SESSION_HISTORIES:
                    loaded = _chat_persistence.load_history(session_id)
                    SESSION_HISTORIES[session_id] = loaded
                return SESSION_HISTORIES[session_id]

        history = await asyncio.to_thread(_load_history_locked)

        # Track access time; evict sessions that have been idle beyond the TTL
        _SESSION_LAST_ACCESS[session_id] = time.monotonic()
        _evict_stale_sessions()

        # We need to create a new message for the user input
        new_human_msg = HumanMessage(content=user_text)

        # Start state with previous history + the new user message
        initial_messages = history + [new_human_msg]

        result = await self.app.ainvoke(
            {
                "messages": initial_messages,
                "next_step": None,
                "tool_calls": None,
                "user_id": user_id,
                "session_id": session_id,
                "current_worker": None,
                "supervisor_decision": None,
            }
        )

        out_messages: List[BaseMessage] = result.get("messages", [])

        state_mgr = get_state_manager()
        session_id_for_state = session_id or "default"
        state_mgr.update_activity(session_id_for_state)

        for msg in out_messages:
            if isinstance(msg, ToolMessage):
                state_mgr.record_tool_use(session_id_for_state, getattr(msg, "name", "unknown"), msg.content or "")

        # Persist updated history under lock to ensure atomic save
        def _save_history_locked():
            with session_lock:
                SESSION_HISTORIES[session_id] = out_messages
                _chat_persistence.save_history(session_id, out_messages)

        await asyncio.to_thread(_save_history_locked)

        assistant_response = ""
        last_tool_output = ""
        tool_call_count = 0
        for msg in reversed(out_messages):
            if isinstance(msg, ToolMessage) and msg.content and not last_tool_output:
                last_tool_output = msg.content
                tool_call_count += 1
            if isinstance(msg, AIMessage) and msg.content:
                if msg.content.startswith("Delegating to "):
                    continue
                assistant_response = msg.content
                break

        if assistant_response:
            refined = await self.refiner.refine(
                original_request=user_text,
                current_response=assistant_response,
                tool_call_count=tool_call_count,
                session_id=session_id,
            )
            return refined.get("response", assistant_response)
        if last_tool_output:
            return f"Encontré resultados de herramienta, pero no pude sintetizarlos automáticamente:\n\n{last_tool_output[:1600]}"
        return "No se pudo generar una respuesta."


# --- Graph lifecycle helpers ---

_graph_instance_lock = threading.Lock()
_graph_instance: AgentGraph = AgentGraph(default_llm, registry)

# Keep graph_app as an alias so existing imports continue to work.
# All call sites should prefer get_graph() so rebuild_graph() takes effect.
graph_app = _graph_instance


def get_graph() -> AgentGraph:
    """Return the current AgentGraph singleton."""
    return _graph_instance


def rebuild_graph() -> AgentGraph:
    """Re-instantiate the AgentGraph singleton (call after roles change)."""
    global _graph_instance, graph_app
    with _graph_instance_lock:
        _graph_instance = AgentGraph(default_llm, registry)
        graph_app = _graph_instance
        logger.info(
            "AgentGraph rebuilt: %d workers loaded.",
            len(role_manager.get_all_workers()),
        )
    return _graph_instance
