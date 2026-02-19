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
    "INSTRUCCIONES CRÍTICAS - DEBES SEGUIR ESTAS REGLAS:\n"
    "1. Analiza el ÚLTIMO mensaje de la conversación.\n"
    "2. Si el último mensaje es una respuesta de un trabajador hacia el usuario (contiene texto legible para el usuario), DEBES responder con 'FINISH' INMEDIATAMENTE.\n"
    "3. Si el usuario acaba de hablar, selecciona el trabajador más adecuado para responder.\n"
    "4. Si un trabajador necesita ayuda de otro, selecciona ese otro trabajador.\n"
    "5. NUNCA vuelvas a seleccionar al mismo trabajador si este ya ha respondido al usuario.\n"
    "6. Si un trabajador ha completado una tarea (ejecutó herramientas, generó contenido, respondió preguntas), DEBES retornar 'FINISH'.\n"
    "7. Para saludos simples ('Hola', 'Buenos días') que ya fueron respondidos, responde 'FINISH'.\n"
    "8. IMPORTANTE: El trabajador 'GeneralAssistant' maneja tareas generales. Si respondió algo útil, usa 'FINISH'.\n"
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

    async def supervisor_node(state: AgentState):
        result = await supervisor_chain.ainvoke(state)
        return result

    return supervisor_node
