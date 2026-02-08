import os
from google import genai
from google.genai import types
from typing import List, Callable, Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

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


        # Register default skills
        from app.skills import system, scheduler, browser, workspace
        
        for tool in system.tools:
            self.register_tool(tool)
        for tool in scheduler.tools:
            self.register_tool(tool)
        for tool in browser.tools:
            self.register_tool(tool)
        for tool in workspace.tools:
            self.register_tool(tool)

    def register_tool(self, tool: Callable):
        """Registers a tool (function) to be used by the agent."""
        self.tools.append(tool)

    async def start_chat(self, session_id: str, history: List[Dict[str, Any]] = None):
        """Starts a new chat session with the configured tools."""
        
        # Tools config
        tool_config = None
        if self.tools:
             tool_config = types.GenerateContentConfig(
                tools=self.tools,
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
        if session_id not in self._chat_sessions:
            await self.start_chat(session_id=session_id)
        
        response = await self._chat_sessions[session_id].send_message(message)
        return response.text

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
