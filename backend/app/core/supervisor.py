from typing import Literal, TypedDict, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from app.core.graph_state import AgentState
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser

# Definir los trabajadores disponibles
WORKERS = ["WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator"]

WORKER_DESCRIPTIONS = {
    "WebNavigator": "Performs web searches (internet) and navigates public websites for information. Use for: searching the web, browsing public websites, reading online articles. IMPORTANT: This is the ONLY worker that can search the internet.",
    "CalendarManager": "Manages calendar, schedules events, and checks availability. Use for: creating calendar events, listing upcoming events, checking schedules.",
    "GeneralAssistant": "Handles Google Drive, Google Sheets, file management, code execution, memory, Telegram, and GitHub MCP. Use for: searching Drive files, managing Google Sheets, reading/writing files, running code, saving memories, sending Telegram messages, GitHub operations (issues, PRs, repos).",
    "ImageGenerator": "Generates images from text descriptions. Use for: creating images, artwork, visual content."
}

# Definir el esquema de salida del Supervisor
class RouteResponse(TypedDict):
    next: Literal["WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator", "FINISH"]

system_prompt = (
    "You are a supervisor responsible for managing a conversation between the following workers:\n{worker_desc}\n\n"
    "CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE RULES:\n"
    "1. Analyze the LAST message in the conversation.\n"
    "2. If the last message is a response from a worker to the user (contains readable text for the user), you MUST respond with 'FINISH' IMMEDIATELY.\n"
    "3. If the user just spoke, select the most appropriate worker to respond.\n"
    "4. If a worker needs help from another, select that other worker.\n"
    "5. NEVER select the same worker again if they have already responded to the user.\n"
    "6. If a worker has completed a task (executed tools, generated content, answered questions), you MUST return 'FINISH'.\n"
    "7. For simple greetings ('Hello', 'Good morning') that have already been responded to, respond 'FINISH'.\n"
    "8. IMPORTANT: After a worker responds, use 'FINISH'.\n"
    "9. Workers execute ONLY ONE tool-call cycle per turn. If you send a worker again, they will do another cycle.\n"
    "10. After a worker completes their tool execution (even if they did just 1 search), you must decide:\n"
    "    - If they found useful information, return 'FINISH' so the user gets the answer\n"
    "    - Only send them again if you genuinely need MORE specific information\n"
    "11. CRITICAL: Don't keep sending workers in a loop! After 1-2 cycles, return FINISH.\n\n"
    "MANDATORY ROUTING RULES - ALWAYS FOLLOW THESE:\n"
    "- SEARCH THE INTERNET / BUSCAR EN INTERNET: ALWAYS use WebNavigator\n"
    "- BROWSING WEBSITES / NAVEGAR SITIOS WEB: ALWAYS use WebNavigator\n"
    "- GOOGLE CALENDAR / CALENDARIO: ALWAYS use CalendarManager\n"
    "- IMAGE GENERATION / GENERAR IMÁGENES: ALWAYS use ImageGenerator\n"
    "- GOOGLE DRIVE / SHEETS: ALWAYS use GeneralAssistant\n"
    "- MEMORY / RECORDS / HECHOS: ALWAYS use GeneralAssistant\n"
    "- CODE EXECUTION: ALWAYS use GeneralAssistant\n"
    "- Default for unknown tasks: GeneralAssistant\n"
)

options = ["FINISH"] + WORKERS

# Usando function calling para estructurar la salida
function_def = {
    "name": "route",
    "description": "Select the next role.",
    "parameters": {
        "title": "routeSchema",
        "type": "object",
        "properties": {
            "next": {
                "title": "Next",
                "type": "string",
                "enum": options,
            }
        },
        "required": ["next"],
    },
}

def create_supervisor_node(llm: BaseChatModel, members: List[str], user_facts: str = ""):
    # Build descriptions block
    worker_desc_block = ""
    for worker_name in members:
        desc = WORKER_DESCRIPTIONS.get(worker_name, "Generic assistant")
        worker_desc_block += f"- {worker_name}: {desc}\n"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("system", "{global_context}"),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(
        options=str(options),
        worker_desc=worker_desc_block,
        global_context=user_facts or "You are NaviBot. Keep worker selection aligned with tool capabilities and role instructions.",
    )

    supervisor_chain = (
        prompt
        | llm.bind_tools(
            tools=[function_def],
            tool_choice="route",
        )
        | JsonOutputFunctionsParser()
    )

    async def supervisor_node(state: AgentState):
        import logging
        logger = logging.getLogger("navibot.supervisor")

        def _route_from_text(text: str):
            lower = (text or "").lower()
            if any(k in lower for k in ["linkedin", "internet", "web", "buscar", "search", "sitio", "url", "navega", "navegar", "profile", "perfil"]):
                return "WebNavigator"
            if any(k in lower for k in ["calendario", "calendar", "evento", "schedule", "agenda"]):
                return "CalendarManager"
            if any(k in lower for k in ["imagen", "image", "dibuja", "generar imagen"]):
                return "ImageGenerator"
            return "GeneralAssistant"
        
        # Get worker call count from state (default to 0 if not present)
        worker_calls = state.get("worker_calls", 0)
        
        # Debug: log last message to understand what supervisor sees
        if state.get("messages"):
            last_msg = state["messages"][-1]
            
            # Check if the last message is a SystemMessage from the summarizer
            # If so, we should NOT finish, but rather continue with the summary as context
            is_summary = "RESUMEN DE CONVERSACIÓN" in str(last_msg.content)
            
            msg_preview = last_msg.content[:200] if hasattr(last_msg, 'content') else str(last_msg)
            logger.info(f"[SUPERVISOR DEBUG] Last message type: {type(last_msg).__name__}, content: {msg_preview}...")
            
            # Also log if this is a worker response
            if hasattr(last_msg, 'name') and last_msg.name in WORKERS:
                logger.info(f"[SUPERVISOR DEBUG] Received response from worker: {last_msg.name}, total worker calls: {worker_calls}")
        
        # Reset worker cycle counter on new user turn
        if state.get("messages") and getattr(state["messages"][-1], "type", "") == "human":
            logger.info("[SUPERVISOR DEBUG] New user turn detected, resetting worker_calls count")
            worker_calls = 0

        # FORCE FINISH after 2 worker cycles to prevent infinite loops
        # EXCEPTION: If the last message was a summary, reset worker_calls because it's a fresh context start
        if state.get("messages") and "RESUMEN DE CONVERSACIÓN" in str(state["messages"][-1].content):
            logger.info("[SUPERVISOR DEBUG] Summary detected, resetting worker_calls count")
            worker_calls = 0
             
        if worker_calls >= 4:
            messages = state.get("messages", []) or []
            has_worker_output = any(
                hasattr(m, "name") and m.name in WORKERS and str(getattr(m, "content", "") or "").strip()
                for m in messages
            )
            if has_worker_output:
                logger.info(f"[SUPERVISOR DEBUG] Worker call soft limit reached ({worker_calls}), forcing FINISH")
                return {"next": "FINISH", "worker_calls": worker_calls}
            logger.warning(
                f"[SUPERVISOR DEBUG] Worker call soft limit reached ({worker_calls}) without worker output. "
                "Allowing one more routing decision."
            )
        
        # Sanitize messages before invoking Gemini-based supervisor.
        # Gemini requires at least one non-empty parts field; empty human messages can trigger 400.
        messages = state.get("messages", []) or []
        sanitized_messages = []
        for m in messages:
            content = str(getattr(m, "content", "") or "").strip()
            if content:
                sanitized_messages.append(m)

        if not sanitized_messages:
            sanitized_messages = [HumanMessage(content="Continue and provide the best next action.")]
        elif getattr(sanitized_messages[-1], "type", "") != "human":
            sanitized_messages.append(HumanMessage(content="Continue and decide the best next worker action."))

        safe_state = dict(state)
        safe_state["messages"] = sanitized_messages
        latest_human = ""
        for m in reversed(sanitized_messages):
            if getattr(m, "type", "") == "human":
                latest_human = str(getattr(m, "content", "") or "")
                break

        forced_route = _route_from_text(latest_human) if latest_human else None
        if forced_route and forced_route != "GeneralAssistant":
            worker_calls += 1
            result = {"next": forced_route, "worker_calls": worker_calls}
            logger.info(f"[SUPERVISOR DEBUG] Deterministic route applied: {result}")
            return result
        result = await supervisor_chain.ainvoke(safe_state)

        # Safety: never finish before at least one worker produces a visible response
        messages = state.get("messages", []) or []
        has_worker_output = any(
            hasattr(m, "name") and m.name in WORKERS and str(getattr(m, "content", "") or "").strip()
            for m in messages
        )
        if isinstance(result, dict) and result.get("next") == "FINISH" and not has_worker_output:
            user_text = ""
            for m in reversed(messages):
                if getattr(m, "type", "") == "human":
                    user_text = str(getattr(m, "content", "") or "")
                    break
            result["next"] = _route_from_text(user_text)
            logger.warning(f"[SUPERVISOR DEBUG] FINISH without worker output blocked, rerouting to {result['next']}")
        
        # If supervisor chooses a worker, increment the counter
        if isinstance(result, dict) and "next" in result and result["next"] in WORKERS:
            worker_calls += 1
            result["worker_calls"] = worker_calls
            logger.info(f"[SUPERVISOR DEBUG] Routing to {result['next']}, incrementing worker_calls to {worker_calls}")
        
        logger.info(f"[SUPERVISOR DEBUG] Routing decision: {result}")
        return result

    return supervisor_node
