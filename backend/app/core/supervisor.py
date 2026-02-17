from typing import Literal, TypedDict, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.graph_state import AgentState
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.utils.function_calling import convert_to_openai_function

# Definir los trabajadores disponibles
WORKERS = ["WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator"]

WORKER_DESCRIPTIONS = {
    "WebNavigator": "Realiza búsquedas en internet y navega por sitios web.",
    "CalendarManager": "Gestiona el calendario, agenda eventos y consulta horarios.",
    "GeneralAssistant": "Maneja charla general, preguntas simples, ejecución de código, gestión de archivos y memoria. Úsalo por defecto para interacciones generales.",
    "ImageGenerator": "Genera imágenes a partir de descripciones."
}

# Definir el esquema de salida del Supervisor
class RouteResponse(TypedDict):
    next: Literal["WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator", "FINISH"]

system_prompt = (
    "Eres un supervisor encargado de gestionar una conversación entre los"
    " siguientes trabajadores:\n{worker_desc}\n\n"
    "Dada la solicitud del usuario, responde con el siguiente trabajador para actuar."
    " Cada trabajador realizará una tarea y responderá con sus resultados y estado."
    " SIEMPRE selecciona un trabajador si la solicitud del usuario requiere una respuesta o acción."
    " Solo responde con FINISH si la tarea ya ha sido completada satisfactoriamente por un trabajador y no se requiere más interacción."
    " Para saludos, preguntas generales o conversaciones, envía a GeneralAssistant."
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
        desc = WORKER_DESCRIPTIONS.get(worker_name, "Asistente genérico")
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

    def supervisor_node(state: AgentState):
        result = supervisor_chain.invoke(state)
        return result

    return supervisor_node
