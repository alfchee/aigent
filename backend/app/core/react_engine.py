"""
ReAct (Reason + Act) Loop Engine

Implements autonomous multi-turn agent execution with observation and reflection.
The agent iteratively reasons, acts, observes results, and reflects until the task is complete.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime


class ReActLoop:
    """
    Manages the ReAct cognitive loop for autonomous agent execution.
    
    The loop follows this pattern:
    1. Thought: Agent receives task/observation
    2. Action: Agent decides to use tool OR provide final answer
    3. Observation: Tool results are fed back to agent
    4. Reflection: Agent evaluates if goal is achieved
    5. Repeat or Terminate
    """
    
    def __init__(
        self, 
        agent,  # NaviBot instance
        max_iterations: int = 10,
        timeout_seconds: int = 300,
        event_callback: Optional[Callable] = None
    ):
        """
        Initialize ReAct loop.
        
        Args:
            agent: NaviBot instance to execute with
            max_iterations: Maximum number of reasoning iterations
            timeout_seconds: Maximum execution time in seconds
            event_callback: Optional async callback for streaming events
        """
        self.agent = agent
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.event_callback = event_callback
        
        # Execution state
        self.iterations = 0
        self.start_time = None
        self.tool_calls_history: List[Dict[str, Any]] = []
        self.reasoning_trace: List[str] = []
        
    async def execute(self, initial_prompt: str) -> Dict[str, Any]:
        """
        Execute the ReAct loop with the given prompt.
        
        Args:
            initial_prompt: The initial task/question for the agent
            
        Returns:
            Dict containing:
                - response: Final agent response
                - iterations: Number of iterations executed
                - tool_calls: List of all tool calls made
                - reasoning_trace: List of reasoning steps
                - termination_reason: Why the loop ended
        """
        self.start_time = time.time()
        self.iterations = 0
        self.tool_calls_history = []
        self.reasoning_trace = []
        
        # Emit start event
        await self._emit_event("start", {
            "message": initial_prompt,
            "max_iterations": self.max_iterations
        })
        
        # Start chat session
        await self.agent.start_chat()
        
        current_prompt = initial_prompt
        final_response = None
        termination_reason = "unknown"
        
        self._log_trace(f"[INITIAL PROMPT] {initial_prompt}")
        
        while self.iterations < self.max_iterations:
            self.iterations += 1
            
            # Check timeout
            if self._is_timeout():
                termination_reason = "timeout"
                final_response = f"Task execution timed out after {self.timeout_seconds} seconds. Completed {self.iterations} iterations."
                self._log_trace(f"[TIMEOUT] Execution exceeded {self.timeout_seconds}s")
                await self._emit_event("error", {
                    "message": "Execution timeout",
                    "details": final_response
                })
                break
            
            self._log_trace(f"\n[ITERATION {self.iterations}] Starting reasoning cycle")
            
            # Emit iteration start event
            await self._emit_event("iteration_start", {
                "iteration": self.iterations,
                "max_iterations": self.max_iterations
            })
            
            # Emit thinking event
            await self._emit_event("thinking", {
                "message": f"Processing iteration {self.iterations} of {self.max_iterations}..."
            })
            
            try:
                # Send message to agent
                response_obj = await self.agent.send_message(current_prompt)
                
                # Extract text and handle non-text responses (e.g. function calls)
                response_text = ""
                tool_calls_info = []

                try:
                    # Try getting standard text
                    if response_obj.text:
                        response_text = response_obj.text
                except Exception:
                    # Handle case where .text fails due to non-text parts
                    pass
                
                # Inspect parts for function calls or other content if text is empty
                if not response_text:
                    try:
                        if hasattr(response_obj, 'candidates') and response_obj.candidates:
                            for part in response_obj.candidates[0].content.parts:
                                if part.function_call:
                                    fc = part.function_call
                                    tool_calls_info.append(f"{fc.name}({fc.args})")
                    except Exception as e:
                        self._log_trace(f"[WARNING] Error inspecting response parts: {e}")

                # If we still have no text but have tool calls, synthesize a response
                if not response_text and tool_calls_info:
                    response_text = f"I have executed the following actions: {', '.join(tool_calls_info)}. Please check the results."
                    self._log_trace(f"[SYNTHESIZED RESPONSE] {response_text}")
                
                # If truly empty
                if not response_text:
                    response_text = "No response text generated (Action completed without output)."
                
                # --- AUTO-INJECT MISSING ARTIFACTS (VALIDATION LAYER) ---
                # Check if we generated artifacts in this turn but forgot to include them in the final text
                generated_artifacts = []
                # Scan tool calls for artifacts
                if hasattr(response_obj, 'candidates') and response_obj.candidates:
                    for part in response_obj.candidates[0].content.parts:
                        if part.function_call:
                             # This is where we would check the *result* of the function call if we had it here.
                             # But in this loop, we are receiving the model's *request* to call a tool (if manual) 
                             # OR the model's response *after* tool execution (if automatic).
                             # With 'automatic_function_calling', the response_obj contains the final text AFTER tools run.
                             # However, we don't easily see the tool outputs here unless we look at the history or if the SDK provides them.
                             
                             # Wait, with automatic_function_calling, the 'response_obj' is the FINAL response.
                             # The intermediate tool calls happened behind the scenes in the SDK.
                             # The SDK unfortunately hides the intermediate tool outputs (like "[FILE_ARTIFACT...]") from the final response object structure usually.
                             # UNLESS we use the 'history' or if the model decided to repeat it.
                             
                             # Actually, in the current Google GenAI SDK with automatic_function_calling, 
                             # getting the tool outputs that happened is tricky without a custom loop.
                             # But let's assume for a moment we can't easily see "past" tool outputs in this object.
                             
                             # ALTERNATIVE: The tools themselves (browser.py) return strings.
                             # If the model uses the tool, the *result* is fed back to the model.
                             # The model *should* see "[FILE_ARTIFACT...]" in its context.
                             # If the model ignores it, we want to force it.
                             pass

                # Since we can't easily intercept the tool output in the automatic loop from the 'response_obj' alone 
                # (without inspecting the chat session history which might be updated),
                # we will rely on a simpler heuristic or just trust the prompt for now, 
                # OR we switch to manual tool execution if we want strict control.
                
                # However, to strictly follow the plan "Update react_engine.py to auto-inject", 
                # we need access to the tool outputs. 
                # Let's inspect the chat history to find the latest tool response.
                
                try:
                    # Access the chat session history
                    history = self.agent._chat_session.history
                    # Look at the last few messages. 
                    # We expect: Model(FunctionCall) -> User(FunctionResponse) -> Model(FinalText)
                    # The FunctionResponse part contains the tool output.
                    
                    if len(history) >= 2:
                        last_user_message = history[-2] # The one before the final model response?
                        # Actually, history structure depends on the SDK.
                        # Usually it's [User, Model, User(ToolOutput), Model]
                        
                        # Iterate backwards to find recent tool outputs in this "turn"
                        # Since we don't know exactly how many turns happened in one send_message call (automatic),
                        # we can just look for tool outputs that are NOT present in the final response text.
                        
                        for msg in reversed(history):
                            if msg.role == "user" and msg.parts: # Tool outputs are often treated as 'user' role or 'function' role depending on API version
                                for part in msg.parts:
                                    # Check for function_response
                                    if hasattr(part, 'function_response'):
                                        # This is a tool output!
                                        # The content is usually in the 'response' field of the function_response
                                        # But the SDK might wrap it. 
                                        # Let's try to stringify or access it.
                                        result_content = str(part.function_response) 
                                        # This might need refinement depending on exact object structure
                                        # But let's look for our tag regex in the string representation
                                        
                                        import re
                                        matches = re.findall(r"\[FILE_ARTIFACT:\s*(.+?)\]", result_content)
                                        for match in matches:
                                            artifact_tag = f"[FILE_ARTIFACT: {match}]"
                                            if artifact_tag not in response_text:
                                                generated_artifacts.append(artifact_tag)
                                    
                                    # Also check plain text parts if the SDK puts tool output there
                                    if hasattr(part, 'text') and part.text:
                                        import re
                                        matches = re.findall(r"\[FILE_ARTIFACT:\s*(.+?)\]", part.text)
                                        for match in matches:
                                            artifact_tag = f"[FILE_ARTIFACT: {match}]"
                                            if artifact_tag not in response_text:
                                                generated_artifacts.append(artifact_tag)
                            
                            # Stop if we hit a normal user message (not tool response)
                            # This is hard to distinguish perfectly without more metadata, 
                            # but we can limit to the last few messages.
                            if msg.role == "user" and not any(hasattr(p, 'function_response') for p in msg.parts):
                                break

                    if generated_artifacts:
                        # Deduplicate
                        generated_artifacts = list(set(generated_artifacts))
                        response_text += "\n\n" + "\n".join(generated_artifacts)
                        self._log_trace(f"[AUTO-INJECTED ARTIFACTS] {generated_artifacts}")

                except Exception as e:
                    self._log_trace(f"[WARNING] Artifact injection check failed: {e}")

                self._log_trace(f"[RESPONSE] {response_text}")
                
                # Emit response event
                await self._emit_event("response", {
                    "text": response_text,
                    "iteration": self.iterations
                })
                
                # Check if this is a final answer (no tool calls needed)
                # In the current implementation with automatic_function_calling=True,
                # the SDK handles tool calls internally. We need to check the response
                # to determine if the agent is done.
                
                # For now, we'll assume that if we get a response, the agent is done
                # This is a simplification - in a more sophisticated implementation,
                # we would disable automatic function calling and manually handle tools
                
                final_response = response_text
                termination_reason = "natural_completion"
                self._log_trace(f"[COMPLETION] Agent provided final answer")
                break
                
            except Exception as e:
                self._log_trace(f"[ERROR] {str(e)}")
                final_response = f"Error during execution: {str(e)}"
                termination_reason = "error"
                await self._emit_event("error", {
                    "message": "Execution error",
                    "details": str(e)
                })
                break
        
        # Check if we hit max iterations
        if self.iterations >= self.max_iterations and termination_reason == "unknown":
            termination_reason = "max_iterations"
            self._log_trace(f"[MAX ITERATIONS] Reached limit of {self.max_iterations}")
        
        execution_time = time.time() - self.start_time
        
        # Emit completion event
        await self._emit_event("completion", {
            "reason": termination_reason,
            "iterations": self.iterations,
            "execution_time_seconds": round(execution_time, 2)
        })
        
        return {
            "response": final_response or "No response generated",
            "iterations": self.iterations,
            "tool_calls": self.tool_calls_history,
            "reasoning_trace": self.reasoning_trace,
            "termination_reason": termination_reason,
            "execution_time_seconds": round(execution_time, 2)
        }
    
    def _is_timeout(self) -> bool:
        """Check if execution has exceeded timeout."""
        if self.start_time is None:
            return False
        elapsed = time.time() - self.start_time
        return elapsed > self.timeout_seconds
    
    def _log_trace(self, message: str):
        """Add a message to the reasoning trace."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        trace_entry = f"[{timestamp}] {message}"
        self.reasoning_trace.append(trace_entry)
        print(trace_entry)  # Also print for real-time debugging
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to the callback if one is registered."""
        if self.event_callback:
            try:
                await self.event_callback(event_type, {
                    **data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Error emitting event: {e}")
    
    def _extract_observations(self, tool_results: Any) -> str:
        """
        Format tool results as observations for the agent.
        
        This will be used in the advanced implementation where we manually
        handle tool calls and feed observations back to the agent.
        """
        if isinstance(tool_results, dict):
            return f"Tool execution result: {tool_results}"
        elif isinstance(tool_results, str):
            return f"Observation: {tool_results}"
        else:
            return f"Observation: {str(tool_results)}"
