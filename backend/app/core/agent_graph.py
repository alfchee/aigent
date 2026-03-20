from typing import Annotated, Dict, List, Optional, TypedDict, Any
import json
import logging
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, FunctionMessage, ToolMessage
from app.core.llm import LLMService, ModelConfig, default_llm
from app.skills.registry import ToolRegistry, registry
from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox
from app.core.roles import role_manager

logger = logging.getLogger("navibot.agent_graph")

# Store full LangChain message history per session
SESSION_HISTORIES: Dict[str, List[BaseMessage]] = {}


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next_step: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    user_id: Optional[str]
    session_id: Optional[str]
    current_worker: Optional[str]


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
                provider=self.llm.default_config.provider,
                model_name=worker_role.model,
                temperature=self.llm.default_config.temperature,
                max_tokens=self.llm.default_config.max_tokens,
                api_key=self.llm.default_config.api_key,
                base_url=self.llm.default_config.base_url,
            )
            available_tools = self.tools.to_openai_tools()
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

        system_prompt = f"""You are NaviBot Supervisor, an intelligent orchestrator.

Context from Memory:
{semantic_context if semantic_context else '(no memory context)'}

Available Workers:
{json.dumps([w.dict() for w in role_manager.get_all_workers()], indent=2)}

Analyze the user's request.
- If it requires a specialist (e.g. coding, research), delegate using the DELEGATE: <role_id> format.
- If you need external information, use a tool.
- If you can answer directly, provide a clear response.
Always respond with exactly ONE of: a direct answer, DELEGATE: <role_id>, or a tool call."""

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
                response = await self.llm.generate(
                    messages=litellm_messages,
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
            }

        choice = response.choices[0].message
        content: str = choice.content or ""
        tool_calls = getattr(choice, "tool_calls", None) or []

        new_messages: List[BaseMessage] = []
        next_step = "end"

        if tool_calls:
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

        elif content.startswith("DELEGATE:"):
            role_id = content.replace("DELEGATE:", "").strip()
            if role_manager.get_worker(role_id):
                next_step = f"worker_{role_id}"
            else:
                new_messages.append(AIMessage(content=f"Error: Worker {role_id} not found."))

        elif content:
            new_messages.append(AIMessage(content=content))
        else:
            new_messages.append(
                AIMessage(
                    content="No encontré una respuesta concluyente en este intento. Intenta reformular o especificar la fuente."
                )
            )

        return {"messages": new_messages, "tool_calls": tool_calls, "next_step": next_step}

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
        step = state.get("next_step")
        if step and (step == "tools" or str(step).startswith("worker_")):
            return step
        return "end"

    async def _sleep_async(self, seconds: float):
        import asyncio
        await asyncio.sleep(seconds)

    async def run_turn(self, user_text: str, user_id: str, session_id: str) -> str:
        global SESSION_HISTORIES

        if session_id not in SESSION_HISTORIES:
            SESSION_HISTORIES[session_id] = []

        history = SESSION_HISTORIES[session_id]
        
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
            }
        )

        out_messages: List[BaseMessage] = result.get("messages", [])
        
        # The out_messages from ainvoke will contain ALL messages (including the initial ones we passed)
        # We update our session history to be exactly this new complete list of messages.
        # This ensures AIMessages with tool_calls and ToolMessages are preserved for the next turn.
        SESSION_HISTORIES[session_id] = out_messages

        # Extract the final textual response for the user
        assistant_response = ""
        last_tool_output = ""
        for msg in reversed(out_messages):
            if isinstance(msg, ToolMessage) and msg.content and not last_tool_output:
                last_tool_output = msg.content
            if isinstance(msg, AIMessage) and msg.content:
                if msg.content.startswith("Delegating to "):
                    continue
                assistant_response = msg.content
                break

        if assistant_response:
            return assistant_response
        if last_tool_output:
            return f"Encontré resultados de herramienta, pero no pude sintetizarlos automáticamente:\n\n{last_tool_output[:1600]}"
        return "No se pudo generar una respuesta."


graph_app = AgentGraph(default_llm, registry)
