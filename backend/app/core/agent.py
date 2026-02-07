import os
from google import genai
from google.genai import types
from typing import List, Callable, Any, Dict, Optional
from dotenv import load_dotenv
from app.core.db import SessionLocal, engine, Base
from app.core.models import ChatSession, ChatMessage
from app.core.serialization import content_to_dict, dict_to_content

load_dotenv()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

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
        # self.sessions = {} # Removed in-memory store in favor of DB

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

    def _prune_history(self, history, max_turns=20):
        """Keeps only the last N turns to avoid context saturation."""
        if len(history) > max_turns * 2:
            return history[-max_turns*2:]
        return history

    def _get_history_from_db(self, session_id: str) -> List[Any]:
        """Retrieves chat history from the database."""
        db = SessionLocal()
        try:
            # Check if session exists
            db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not db_session:
                print(f"[DB] Session not found for session_id={session_id}")
                return []
            
            # Get messages
            messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
            
            # Convert back to SDK Content objects
            print(f"[DB] Loaded {len(messages)} messages for session_id={session_id}")
            return [dict_to_content(msg.content) for msg in messages]
        except Exception as e:
            print(f"Error retrieving history: {e}")
            return []
        finally:
            db.close()

    def _save_history_to_db(self, session_id: str, history: List[Any]):
        """Saves the latest chat history to the database."""
        db = SessionLocal()
        try:
            # Ensure session exists
            db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not db_session:
                db_session = ChatSession(id=session_id)
                db.add(db_session)
                db.commit()
                print(f"[DB] Created chat_session for session_id={session_id}")
            
            # Validation: Check for empty history if we expect something
            if not history:
                print(f"[DB] Warning: Attempting to save empty history for session {session_id}")
            
            # Count existing messages before delete
            existing_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
            
            # Simple heuristic: If we have significantly fewer messages than before, and not pruning, log warning
            if len(history) < existing_count and existing_count < 20: # Assuming pruning threshold 20
                 print(f"[DB] Warning: New history ({len(history)}) is smaller than existing ({existing_count}) for session {session_id}. Potential data loss?")

            # Delete old messages
            db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
            
            new_messages = []
            for i, msg in enumerate(history):
                try:
                    # Serialize content
                    msg_dict = content_to_dict(msg)
                    if not msg_dict.get("parts"):
                        print(f"[DB] Warning: Message {i} has no parts after serialization. Role: {msg.role}")
                    
                    new_messages.append(ChatMessage(
                        session_id=session_id,
                        role=msg_dict["role"],
                        content=msg_dict
                    ))
                except Exception as e:
                    print(f"[DB] Error serializing message {i}: {e}")

            if new_messages:
                db.add_all(new_messages)
                db.commit()
                print(f"[DB] Successfully saved {len(new_messages)} messages for session {session_id}")
            else:
                print(f"[DB] No messages to save for session {session_id}")
            
        except Exception as e:
            print(f"[DB] Critical Error saving history: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

    async def start_chat(self, session_id: str = "default", history: List[Dict[str, Any]] = None):
        """Starts a new chat session with the configured tools and history."""
        
        # Load history from session if not provided
        if history is None:
            history = self._get_history_from_db(session_id)
        
        # Prune history
        history = self._prune_history(history)
        print(f"[Agent] start_chat session_id={session_id} history_count={len(history)}")
        
        # Prepare config arguments
        config_args = {
            "system_instruction": self._load_system_instruction()
        }

        # Add tools if available
        if self.tools:
             config_args["tools"] = self.tools
             config_args["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=False
             )
        
        # Create configuration object
        tool_config = types.GenerateContentConfig(**config_args)

        # Create async chat session
        self._chat_session = self.client.aio.chats.create(
            model=self.model_name,
            config=tool_config,
            history=history
        )

    def _load_system_instruction(self) -> str:
        """Loads the system instruction/SOPs."""
        try:
            # Try to load from prompts.py (which we created as a text file essentially)
            # In a real app, this might be a python string constant, but we saved it as a file content.
            # Let's read it if it exists, or define it here.
            
            # Since we saved prompts.py as a text file with markdown content in the previous step (Write tool),
            # we should read it. However, the user might expect it to be a python module.
            # Let's check if we wrote it as valid python or just text. 
            # We wrote raw markdown to a .py file which is invalid python but readable as text.
            # Ideally we should have saved it as .md or a python string. 
            # Let's fix this by reading it as a file.
            
            sop_path = os.path.join(os.path.dirname(__file__), "prompts.py")
            if os.path.exists(sop_path):
                with open(sop_path, "r") as f:
                    return f.read()
            return "You are a helpful AI assistant with browser capabilities."
        except Exception as e:
            print(f"Error loading system prompt: {e}")
            return "You are a helpful AI assistant."

    async def send_message(self, message: str, session_id: str = "default") -> Any:
        if not self._chat_session:
            await self.start_chat(session_id=session_id)
        
        print(f"[Agent] send_message session_id={session_id}")
        response = await self._chat_session.send_message(message)
        
        # Try to get comprehensive history (including tool calls) if available
        # Some SDK versions hide tool calls in .history property
        history_to_save = []
        try:
            # Check for _comprehensive_history (private attribute in some versions)
            if hasattr(self._chat_session, '_comprehensive_history'):
                history_to_save = self._chat_session._comprehensive_history
            # Check for get_history(curated=False) which is default but let's be explicit if needed
            # or just use get_history() as fallback
            if not history_to_save:
                history_to_save = self._chat_session.get_history()
        except Exception as e:
             print(f"[Agent] Error retrieving comprehensive history: {e}")
             history_to_save = self._chat_session.get_history()

        print(f"[Agent] save_history session_id={session_id} history_count={len(history_to_save)}")
        self._save_history_to_db(session_id, history_to_save)
        
        return response

    async def send_message_with_react(
        self, 
        message: str,
        session_id: str = "default",
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
            session_id=session_id,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            event_callback=event_callback
        )
        
        return await react_loop.execute(message)
