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
        self._chat_session = None


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

    async def start_chat(self, history: List[Dict[str, Any]] = None):
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
        self._chat_session = self.client.aio.chats.create(
            model=self.model_name,
            config=tool_config,
            history=history
        )

    async def send_message(self, message: str) -> str:
        if not self._chat_session:
            await self.start_chat()
        
        response = await self._chat_session.send_message(message)
        return response.text
