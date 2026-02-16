import os
import logging
import functools
from typing import Literal

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, create_react_agent

from app.core.graph_state import AgentState
from app.core.skill_loader import SkillLoader
from app.core.supervisor import create_supervisor_node, WORKERS

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logger = logging.getLogger(__name__)

# Prompts de Sistema para cada Trabajador
WORKER_PROMPTS = {
    "WebNavigator": (
        "Eres un especialista en navegación web. Tu objetivo es buscar información, "
        "leer contenido de páginas y sintetizar respuestas precisas.\n"
        "Instrucciones:\n"
        "- Utiliza 'search' para encontrar fuentes relevantes.\n"
        "- Utiliza 'browser' para navegar y extraer contenido detallado cuando sea necesario.\n"
        "- Si la información es extensa, resume los puntos clave.\n"
        "- Cita las fuentes (URLs) de donde obtuviste la información."
    ),
    "CalendarManager": (
        "Eres el gestor de calendario y agenda. Tu responsabilidad es organizar el tiempo del usuario.\n"
        "Instrucciones:\n"
        "- Siempre verifica la fecha y hora actual antes de agendar o consultar eventos relativos (como 'mañana').\n"
        "- Usa formato ISO 8601 (YYYY-MM-DDTHH:MM:SS) para las fechas.\n"
        "- Al listar eventos, sé claro y ordenado.\n"
        "- Si hay conflictos de horario, avisa al usuario."
    ),
    "GeneralAssistant": (
        "Eres un asistente general versátil. Te encargas de tareas del sistema, ejecución de código, "
        "gestión de archivos y memoria.\n"
        "Instrucciones:\n"
        "- Si te piden ejecutar código, usa las herramientas de 'code_execution'.\n"
        "- Para manipular archivos, usa las herramientas de 'workspace'.\n"
        "- Si necesitas recordar algo para el futuro, usa las herramientas de 'memory'.\n"
        "- Sé proactivo y busca la solución más eficiente."
    )
}

class AgentGraph:
    def __init__(self, model_name: str = "gemini-2.0-flash", extra_tools: list = None):
        """
        Inicializa el Grafo Multi-Agente con Supervisor.
        """
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.extra_tools = extra_tools or []
        
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. AgentGraph may fail to initialize correctly.")
            
        # 1. Cargar Herramientas Agrupadas
        self.loader = SkillLoader()
        self.skills_map = self.loader.load_skills_map()
        
        # Inyectar herramientas extra en un módulo virtual 'extra_tools'
        if self.extra_tools:
            self.skills_map["extra_tools"] = self.extra_tools

        # 2. Configurar Modelo
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=0,
            convert_system_message_to_human=True
        )
        
        # 3. Definir Herramientas por Trabajador
        # Mapeo de Workers a Módulos de Skills
        self.worker_skills = {
            "WebNavigator": ["browser", "search", "reader"],
            "CalendarManager": ["calendar", "scheduler"],
            "GeneralAssistant": ["workspace", "code_execution", "google_drive", "memory", "telegram", "extra_tools"] 
            # GeneralAssistant se lleva el resto o lo que definamos
        }

        # 4. Construir el Grafo
        self.graph = self._build_graph()

    def _create_agent_node(self, agent_name: str, tools: list):
        """Helper para crear un nodo agente."""
        # Usamos create_react_agent de langgraph prebuilt que ya maneja el ciclo ReAct
        # Pero necesitamos adaptarlo para que funcione como un nodo en nuestro grafo supervisado
        # El nodo debe recibir el estado, invocar al agente, y devolver la actualización del estado.
        
        agent = create_react_agent(self.llm, tools)
        
        def agent_node(state: AgentState):
            result = agent.invoke(state)
            # El resultado de create_react_agent es el estado final.
            # Queremos añadir un mensaje indicando quién respondió si es necesario, 
            # pero create_react_agent ya añade los mensajes al historial.
            # Simplemente retornamos los nuevos mensajes.
            
            # LangGraph prebuilt agent returns a dict with keys like 'messages'
            return {"messages": [
                HumanMessage(content=f"Result from {agent_name}:", name=agent_name)
            ] + result["messages"][-1:]} # Solo el último mensaje (respuesta final del agente)
            
            # NOTA: Esta es una simplificación. En una implementación real robusta, 
            # querríamos pasar toda la cadena de pensamiento o manejar el estado con más cuidado.
            # Para este MVP, dejaremos que el agente ejecute y devuelva su conclusión.

        return agent_node

    def _build_graph(self):
        """
        Construye el StateGraph Multi-Agente.
        """
        workflow = StateGraph(AgentState)

        # 1. Crear Nodo Supervisor
        supervisor_node = create_supervisor_node(self.llm, WORKERS)
        workflow.add_node("supervisor", supervisor_node)

        # 2. Crear Nodos de Trabajadores
        for worker_name in WORKERS:
            # Recolectar herramientas para este trabajador
            worker_tools = []
            skill_names = self.worker_skills.get(worker_name, [])
            
            for skill in skill_names:
                if skill in self.skills_map:
                    worker_tools.extend(self.skills_map[skill])
            
            # Si no hay herramientas específicas, dar un set por defecto o vacío (para chat)
            if not worker_tools and worker_name == "GeneralAssistant":
                 # Fallback: darle todas las que no estén asignadas explícitamente a otros?
                 # O simplemente herramientas básicas.
                 pass

            # Crear el agente (usando prebuilt ReAct agent para simplificar la lógica interna del worker)
            # Nota: create_react_agent devuelve un CompiledGraph.
            # Lo envolvemos en una función nodo.
            
            # Obtener prompt del sistema
            system_prompt = WORKER_PROMPTS.get(worker_name, "Eres un asistente útil.")
            
            worker_agent = create_react_agent(self.llm, worker_tools, prompt=system_prompt)
            
            # Definir la función del nodo
            # Usamos functools.partial para capturar worker_agent en el closure correctamente
            async def node_func(state: AgentState, agent=worker_agent, name=worker_name):
                # Invocar al agente con el estado actual
                result = await agent.ainvoke(state)
                # Devolver el último mensaje generado por el agente
                return {"messages": [
                    HumanMessage(content=result["messages"][-1].content, name=name)
                ]}
            
            workflow.add_node(worker_name, node_func)

        # 3. Definir Flujo (Aristas)
        # El punto de entrada es el supervisor
        workflow.add_edge(START, "supervisor")

        # El supervisor decide a quién ir
        conditional_map = {k: k for k in WORKERS}
        conditional_map["FINISH"] = END
        
        workflow.add_conditional_edges(
            "supervisor",
            lambda x: x["next"],
            conditional_map
        )

        # Los trabajadores siempre vuelven al supervisor para reportar
        for worker_name in WORKERS:
            workflow.add_edge(worker_name, "supervisor")

        return workflow.compile()

    def get_runnable(self):
        return self.graph
