from typing import Literal, TypedDict, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.graph_state import AgentState
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.utils.function_calling import convert_to_openai_function

# Definir los trabajadores disponibles
WORKERS = ["WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator"]

WORKER_DESCRIPTIONS = {
    "WebNavigator": "Performs web searches (internet) and navigates public websites for information. Use for: searching the web, browsing public websites, reading online articles.",
    "CalendarManager": "Manages calendar, schedules events, and checks availability. Use for: creating calendar events, listing upcoming events, checking schedules.",
    "GeneralAssistant": "Handles Google Drive, Google Sheets, file management, code execution, memory, and Telegram. Use for: searching Drive files, managing Google Sheets, reading/writing files, running code, saving memories, sending Telegram messages. This is the DEFAULT for most tasks including Google Workspace operations.",
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
    "8. IMPORTANT: The 'GeneralAssistant' worker handles general tasks. If it provided useful response, use 'FINISH'.\n\n"
    "ROUTING RULES - FOLLOW THESE MANDATORY RULES:\n"
    "- For GOOGLE DRIVE requests (find folder, search files, list files, create folders): use GeneralAssistant\n"
    "- For GOOGLE SHEETS/SPREADSHEET requests: use GeneralAssistant\n"
    "- For GOOGLE CALENDAR requests: use CalendarManager\n"
    "- For INTERNET WEB SEARCH (not Drive): use WebNavigator\n"
    "- For BROWSING PUBLIC WEBSITES: use WebNavigator\n"
    "- For IMAGE GENERATION: use ImageGenerator\n"
    "- For CODE EXECUTION, FILE MANAGEMENT, MEMORY, TELEGRAM: use GeneralAssistant\n"
    "- Default for most tasks: GeneralAssistant\n"
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

def create_supervisor_node(llm: ChatGoogleGenerativeAI, members: List[str], user_facts: str = ""):
    facts_section = ""
    if user_facts:
        facts_section = f"\n\nHere are some facts about the user you should keep in mind:\n{user_facts}"

    # Build descriptions block
    worker_desc_block = ""
    for worker_name in members:
        desc = WORKER_DESCRIPTIONS.get(worker_name, "Generic assistant")
        worker_desc_block += f"- {worker_name}: {desc}\n"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt + facts_section),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(options=str(options), worker_desc=worker_desc_block)

    supervisor_chain = (
        prompt
        | llm.bind_tools(
            tools=[function_def],
            tool_choice="route",
        )
        | JsonOutputFunctionsParser()
    )

    async def supervisor_node(state: AgentState):
        result = await supervisor_chain.ainvoke(state)
        return result

    return supervisor_node
