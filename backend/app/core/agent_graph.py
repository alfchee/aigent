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
from app.core.model_orchestrator import ModelOrchestrator

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logger = logging.getLogger(__name__)

# System Prompts for each Worker
WORKER_PROMPTS = {
    "WebNavigator": (
        "You are a web navigation specialist. Your goal is to search for information on the public internet, "
        "browse websites, and synthesize accurate responses.\n"
        "Instructions:\n"
        "- Use 'search_brave' or 'search_duckduckgo_fallback' to find relevant sources on the web.\n"
        "- Use 'navigate', 'get_page_content', 'screenshot' to browse and extract detailed content from public websites.\n"
        "- If the information is extensive, summarize the key points.\n"
        "- Cite the sources (URLs) where you got the information.\n"
        "IMPORTANT: Do NOT use these tools for Google Drive or Google Sheets - those are handled by GeneralAssistant."
    ),
    "CalendarManager": (
        "You are a calendar and schedule manager. Your responsibility is to organize the user's time.\n"
        "Instructions:\n"
        "- Always verify the current date and time before scheduling or checking events relative to dates (like 'tomorrow').\n"
        "- Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS) for dates.\n"
        "- When listing events, be clear and organized.\n"
        "- If there are scheduling conflicts, notify the user."
    ),
    "GeneralAssistant": (
        "You are a versatile general assistant. You handle Google Workspace, file management, code execution, memory, and Telegram.\n"
        "Instructions:\n"
        "- GOOGLE DRIVE: Use 'search_drive', 'list_drive_files', 'download_file_from_drive', 'create_drive_folder', 'create_drive_file', 'delete_drive_file', 'copy_drive_file', 'get_drive_file_info', 'share_drive_file' to manage Drive files.\n"
        "- GOOGLE SHEETS: Use 'create_google_spreadsheet', 'update_sheet_data' for spreadsheet operations.\n"
        "- CODE EXECUTION: Use 'execute_python' to run code.\n"
        "- FILE MANAGEMENT: Use 'workspace' tools to manage session files.\n"
        "- MEMORY: Use 'recall_facts', 'save_fact' to store/retrieve long-term memory.\n"
        "- TELEGRAM: Use 'send_telegram_message' to send messages.\n"
        "- Be proactive and seek the most efficient solution.\n"
        "IMPORTANT: For web searches (internet), use WebNavigator. For calendar, use CalendarManager."
    ),
    "ImageGenerator": (
        "You are a specialist in generating images from textual descriptions.\n"
        "Instructions:\n"
        "- Use the 'generate_image' tool to create images.\n"
        "- If details are missing (style, aspect ratio), ask for clarification.\n"
        "- Return the result indicating the path of the generated file."
    )
}

class AgentGraph:
    def __init__(self, model_name: str = "gemini-2.0-flash", extra_tools: list = None, user_facts: str = "", checkpointer = None):
        """
        Inicializa el Grafo Multi-Agente con Supervisor.
        """
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.extra_tools = extra_tools or []
        self.user_facts = user_facts
        self.checkpointer = checkpointer
        self.orchestrator = ModelOrchestrator()
        
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. AgentGraph may fail to initialize correctly.")
            
        # 1. Cargar Herramientas Agrupadas
        self.loader = SkillLoader()
        self.skills_map = self.loader.load_skills_map()
        
        # Inyectar herramientas extra en un módulo virtual 'extra_tools'
        if self.extra_tools:
            self.skills_map["extra_tools"] = self.extra_tools

        # 2. Configurar Modelo (Legacy/Fallback)
        # We keep self.llm for backward compatibility or default usage, but nodes will use specific LLMs
        self.llm = self._get_llm("supervisor") 
        
        # 3. Definir Herramientas por Trabajador
        # Mapeo de Workers a Módulos de Skills
        self.worker_skills = {
            "WebNavigator": ["browser", "search", "reader"],
            "CalendarManager": ["calendar", "scheduler"],
            "GeneralAssistant": ["workspace", "code_execution", "google_drive", "memory", "telegram", "extra_tools"],
            "ImageGenerator": ["image_generation"]
            # GeneralAssistant se lleva el resto o lo que definamos
        }

        # 4. Construir el Grafo
        self.graph = self._build_graph()

    def _get_llm(self, role_name: str) -> ChatGoogleGenerativeAI:
        """
        Returns a configured LLM instance for a specific role/worker.
        """
        # Map worker names to config roles
        config_role = "supervisor"
        if role_name == "WebNavigator":
            config_role = "search_worker"
        elif role_name == "CalendarManager":
            config_role = "scheduled_worker"
        elif role_name == "GeneralAssistant":
            config_role = "code_worker"
        elif role_name == "ImageGenerator":
            config_role = "image_worker"
        elif role_name == "supervisor":
            config_role = "supervisor"
            
        # For supervisor, we prefer the model_name passed in __init__ (which comes from session/request)
        # UNLESS it's the default/generic one, in which case we might want to check the config.
        # But to be safe and respect explicit overrides, we use self.model_name for supervisor.
        # Actually, let's use the orchestrator to decide based on the role.
        # If self.model_name is specifically set to something non-default by the caller, we should use it.
        # But here we assume self.model_name is the "Supervisor" model.
        
        final_model = self.model_name if role_name == "supervisor" else self.orchestrator.get_model_for_role(config_role)
        
        return ChatGoogleGenerativeAI(
            model=final_model,
            google_api_key=self.api_key,
            temperature=0,
            convert_system_message_to_human=True
        )

    def _create_agent_node(self, agent_name: str, tools: list):
        """Helper para crear un nodo agente."""
        # Usamos create_react_agent de langgraph prebuilt que ya maneja el ciclo ReAct
        # Pero necesitamos adaptarlo para que funcione como un nodo en nuestro grafo supervisado
        # El nodo debe recibir el estado, invocar al agente, y devolver la actualización del estado.
        
        # Use specific LLM for this agent
        agent_llm = self._get_llm(agent_name)
        agent = create_react_agent(agent_llm, tools)
        
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
        # Use specific LLM for supervisor
        supervisor_llm = self._get_llm("supervisor")
        supervisor_node = create_supervisor_node(supervisor_llm, WORKERS, user_facts=self.user_facts)
        
        # Logging wrapper for Supervisor node
        supervisor_call_count = {}  # Track calls per user message
        
        async def logging_supervisor_node(state: AgentState):
            import logging
            logger = logging.getLogger("navibot.graph")
            
            # Get or initialize the supervisor call count for this thread
            messages = state.get("messages", [])
            user_msg_count = sum(1 for m in messages if hasattr(m, "type") and m.type == "human")
            
            # Get the last message to check if it's from a worker
            last_msg = state.get("messages", [])[-1] if state.get("messages") else None
            is_worker_response = hasattr(last_msg, "name") and last_msg.name in WORKERS
            
            # Force FINISH if this is the second supervisor call (worker already responded)
            if user_msg_count > 0 and is_worker_response:
                logger.info("[Graph] Supervisor forcing FINISH - worker already responded")
                return {"next": "FINISH"}
            
            logger.info(f"[Graph] Supervisor Input State: {state.get('messages')[-1] if state.get('messages') else 'Empty'}")
            
            result = await supervisor_node(state)
            
            # Log routing decision
            if isinstance(result, dict) and "next" in result:
                logger.info(f"Supervisor decided to call: -{result['next']} with arguments: {state.get('messages', [])[-1].content[:200] if state.get('messages') else 'Empty'}")
            elif hasattr(result, "next"):
                logger.info(f"Supervisor decided to call: -{result.next} with arguments: {state.get('messages', [])[-1].content[:200] if state.get('messages') else 'Empty'}")
            else:
                logger.info(f"Supervisor Result: {result}")
                
            return result
            
        workflow.add_node("supervisor", logging_supervisor_node)

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
            system_prompt = WORKER_PROMPTS.get(worker_name, "You are a helpful assistant.")
            
            # Inyectar hechos del usuario si es el asistente general
            if worker_name == "GeneralAssistant" and self.user_facts:
                system_prompt += f"\n\nFacts about the user:\n{self.user_facts}"
            
            # Use specific LLM for this worker
            worker_llm = self._get_llm(worker_name)
            worker_agent = create_react_agent(worker_llm, worker_tools, prompt=system_prompt)
            
            # Definir la función del nodo
            # Usamos functools.partial para capturar worker_agent en el closure correctamente
            async def node_func(state: AgentState, agent=worker_agent, name=worker_name):
                import logging
                logger = logging.getLogger(f"navibot.worker.{name}")
                
                # Log entry
                last_msg = state["messages"][-1]
                logger.info(f"[Graph Worker:{name}] Processing: {last_msg.content[:100]}...")
                
                # Invocar al agente con el estado actual
                result = await agent.ainvoke(state)
                
                # Log output
                last_response = result["messages"][-1]
                logger.info(f"[Graph Worker:{name}] Completed. Response: {last_response.content[:100]}...")
                
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

        return workflow.compile(checkpointer=self.checkpointer)

    def get_runnable(self):
        return self.graph
