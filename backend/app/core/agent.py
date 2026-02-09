import os
from pathlib import Path
from google import genai
from google.genai import types
from typing import List, Callable, Any, Dict, Optional
from dotenv import load_dotenv

from app.core.persistence import load_chat_history, wrap_tool

load_dotenv()

SEARCH_POLICY = """
## Política de búsqueda web (prioridad estricta)
Cuando el usuario solicite información externa o búsqueda web, sigue este orden:
1. Usa la herramienta nativa de Google Grounding (google_search_retrieval).
2. Si falla o no está disponible, usa search_brave.
3. Si falla o no hay resultados útiles, usa search_duckduckgo_fallback.
Si el resultado requiere detalles que no están en el snippet (tablas, listados, cifras), usa read_web_content con la URL relevante.
Devuelve enlaces citables y evita inventar resultados.
""".strip()

class NaviBot:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY not found in environment variables.")
            # We initialize with a placeholder if missing to avoid crash until usage
            self.client = genai.Client(api_key="MISSING")
        else:
            self.client = genai.Client(api_key=api_key)
        
        self.tools: List[Callable] = []
        self.model_name = model_name
        self._chat_sessions: Dict[str, Any] = {}
        self._tool_reference: Optional[str] = None


        # Register default skills
        from app.skills import scheduler, browser, workspace, search, reader, code_execution
        
        for tool in scheduler.tools:
            self.register_tool(tool)
        for tool in browser.tools:
            self.register_tool(tool)
        for tool in workspace.tools:
            self.register_tool(tool)
        for tool in search.tools:
            self.register_tool(tool)
        for tool in reader.tools:
            self.register_tool(tool)
        for tool in code_execution.tools:
            self.register_tool(tool)

    def register_tool(self, tool: Callable):
        """Registers a tool (function) to be used by the agent."""
        self.tools.append(wrap_tool(tool))

    def _load_tool_reference(self) -> str:
        if self._tool_reference is not None:
            return self._tool_reference
        root = Path(__file__).resolve().parents[3]
        doc_path = root / "docs" / "backend_overview.md"
        if not doc_path.exists():
            self._tool_reference = ""
            return self._tool_reference
        try:
            text = doc_path.read_text(encoding="utf-8")
        except Exception:
            self._tool_reference = ""
            return self._tool_reference
        marker = "## Tool and Skill Reference (Agent Tooling)"
        if marker not in text:
            self._tool_reference = ""
            return self._tool_reference
        after = text.split(marker, 1)[1]
        section = f"{marker}{after}"
        lines = section.splitlines()
        collected = [lines[0]]
        for line in lines[1:]:
            if line.startswith("## ") and line != lines[0]:
                break
            collected.append(line)
        self._tool_reference = "\n".join(collected).strip()
        return self._tool_reference

    def _build_system_instruction(self, tool_reference: str) -> str:
        parts = [part for part in [tool_reference, SEARCH_POLICY] if part]
        return "\n\n".join(parts).strip()

    def _google_grounding_enabled(self) -> bool:
        value = os.getenv("ENABLE_GOOGLE_GROUNDING", "true").lower()
        return value not in {"0", "false", "no"}

    def _google_grounding_mode(self) -> str:
        return os.getenv("GOOGLE_GROUNDING_MODE", "auto").lower()

    async def start_chat(self, session_id: str, history: List[Dict[str, Any]] = None):
        """Starts a new chat session with the configured tools."""
        from app.skills.filesystem import get_filesystem_tools
        from app.core.persistence import wrap_tool

        if history is None:
            history = load_chat_history(session_id)
        
        # Tools config
        tool_config = None
        
        # 1. Get Global Tools
        current_tools = self.tools.copy() if self.tools else []
        
        # 2. Get Session-Specific Tools (Filesystem)
        fs_tools = get_filesystem_tools(session_id)
        for tool in fs_tools:
            current_tools.append(wrap_tool(tool))
            
        tools_payload = current_tools
        if self._google_grounding_enabled():
            grounding_mode = self._google_grounding_mode()
            if grounding_mode == "only":
                tools_payload = [{"google_search_retrieval": {}}]
            elif grounding_mode == "auto" and not current_tools:
                tools_payload = [{"google_search_retrieval": {}}]

        if tools_payload:
            tool_reference = self._load_tool_reference()
            system_instruction = self._build_system_instruction(tool_reference)
            tool_config = types.GenerateContentConfig(
                tools=tools_payload,
                system_instruction=system_instruction if system_instruction else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False
                )
            )

        # Create async chat session
        self._chat_sessions[session_id] = self.client.aio.chats.create(
            model=self.model_name,
            config=tool_config,
            history=history
        )

    async def send_message(self, message: str) -> str:
        from app.core.runtime_context import get_session_id

        session_id = get_session_id()
        await self.ensure_session(session_id)
        
        response = await self._chat_sessions[session_id].send_message(message)
        return response.text

    async def ensure_session(self, session_id: str):
        """Ensures a chat session exists, loading from history if needed."""
        if session_id not in self._chat_sessions:
            await self.start_chat(session_id=session_id)

    def get_history(self, session_id: str) -> List[Any]:
        """Returns the chat history for a session."""
        if session_id in self._chat_sessions:
            chat = self._chat_sessions[session_id]
            # Handle AsyncChat which uses get_history() method instead of history property
            if hasattr(chat, "get_history") and callable(chat.get_history):
                return chat.get_history()
            # Fallback for other chat types or older SDK versions
            if hasattr(chat, "history"):
                return chat.history
            
            # If neither exists, log warning and return empty list
            print(f"Warning: Could not access history for session {session_id}")
            return []
        return []

    async def send_message_with_react(
        self, 
        message: str,
        max_iterations: int = 10,
        timeout_seconds: int = 300,
        event_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Execute message with ReAct (Reason + Act) loop.
        
        The agent will iteratively reason, act, observe, and reflect
        until the task is complete or limits are reached.
        
        Args:
            message: The task/question for the agent
            max_iterations: Maximum reasoning cycles (default: 10)
            timeout_seconds: Maximum execution time (default: 300s)
            event_callback: Optional async callback for streaming events
            
        Returns:
            Dict containing:
                - response: Final agent response
                - iterations: Number of iterations executed
                - tool_calls: List of all tool calls made
                - reasoning_trace: List of reasoning steps
                - termination_reason: Why the loop ended
                - execution_time_seconds: Total execution time
        """
        from app.core.react_engine import ReActLoop
        
        react_loop = ReActLoop(
            agent=self,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            event_callback=event_callback
        )
        
        return await react_loop.execute(message)
