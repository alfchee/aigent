from typing import Literal, TypedDict, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.graph_state import AgentState
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.utils.function_calling import convert_to_openai_function

# Definir los trabajadores disponibles
WORKERS = ["WebNavigator", "CalendarManager", "GeneralAssistant"]

# Definir el esquema de salida del Supervisor
class RouteResponse(TypedDict):
    next: Literal["WebNavigator", "CalendarManager", "GeneralAssistant", "FINISH"]

system_prompt = (
    "Eres un supervisor encargado de gestionar una conversación entre los"
    " siguientes trabajadores: {members}. Dada la solicitud del usuario,"
    " responde con el siguiente trabajador para actuar. Cada trabajador realizará"
    " una tarea y responderá con sus resultados y estado. Cuando termines,"
    " responde con FINISH."
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

def create_supervisor_node(llm: ChatGoogleGenerativeAI, members: List[str]):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(options=str(options), members=", ".join(members))

    supervisor_chain = (
        prompt
        | llm.bind_tools(
            tools=[function_def],
            tool_choice="route",
        )
        | JsonOutputFunctionsParser()
    )

    def supervisor_node(state: AgentState):
        result = supervisor_chain.invoke(state)
        return result

    return supervisor_node
