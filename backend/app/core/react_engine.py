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
                response = await self.agent.send_message(current_prompt)
                
                self._log_trace(f"[RESPONSE] {response}")
                
                # Emit response event
                await self._emit_event("response", {
                    "text": response,
                    "iteration": self.iterations
                })
                
                # Check if this is a final answer (no tool calls needed)
                # In the current implementation with automatic_function_calling=True,
                # the SDK handles tool calls internally. We need to check the response
                # to determine if the agent is done.
                
                # For now, we'll assume that if we get a response, the agent is done
                # This is a simplification - in a more sophisticated implementation,
                # we would disable automatic function calling and manually handle tools
                
                final_response = response
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
