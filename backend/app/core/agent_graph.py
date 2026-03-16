from typing import Annotated, Dict, List, Literal, Optional, Sequence, TypedDict, Union, Any
import json
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, FunctionMessage
from app.core.llm import LLMService, ModelConfig
from app.skills.registry import ToolRegistry, registry

from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox

from app.core.roles import role_manager

# Define the state of the graph
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], "messages"]
    next_step: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    user_id: Optional[str]
    session_id: Optional[str]
    current_worker: Optional[str] # Track which worker is active

class AgentGraph:
    """
    Main LangGraph orchestrator implementing the Supervisor-Worker pattern.
    """
    def __init__(self, llm_service: LLMService, tool_registry: ToolRegistry):
        self.llm = llm_service
        self.tools = tool_registry
        self.workflow = StateGraph(AgentState)
        self._build_graph()

    def get_memory_controller(self, user_id: str) -> MemoryController:
        # TODO: Cache controllers or use a factory
        return MemoryController(user_id=user_id)

    def _build_graph(self):
        """Construct the graph nodes and edges."""
        # Add nodes
        self.workflow.add_node("supervisor", self.supervisor_node)
        self.workflow.add_node("tools", self.tools_node)
        
        # Add dynamic worker nodes
        workers = role_manager.get_all_workers()
        for worker in workers:
            self.workflow.add_node(f"worker_{worker.role_id}", self.create_worker_node(worker))

        # Set entry point
        self.workflow.set_entry_point("supervisor")

        # Add conditional edges
        self.workflow.add_conditional_edges(
            "supervisor",
            self.should_continue,
            {
                "continue": "tools",
                "end": END,
                **{f"worker_{w.role_id}": f"worker_{w.role_id}" for w in workers}
            }
        )

        # Add edges from workers back to supervisor (or tools if needed)
        for worker in workers:
            self.workflow.add_edge(f"worker_{worker.role_id}", "supervisor")

        # Add edge from tools back to supervisor
        self.workflow.add_edge("tools", "supervisor")

        # Compile the graph
        self.app = self.workflow.compile()
    
    def create_worker_node(self, worker_role):
        """Factory for worker node functions."""
        async def worker_func(state: AgentState) -> Dict[str, Any]:
            # Similar to supervisor but scoped skills and prompt
            # For simplicity in this iteration, workers just process and return to supervisor
            # Real implementation would have specialized logic
            return {"messages": [AIMessage(content=f"Worker {worker_role.name} processed request.")]}
        return worker_func

    async def supervisor_node(self, state: AgentState) -> Dict[str, Any]:
        """
        The Supervisor node decides the next action based on the conversation history.
        It uses the LLM to either respond directly or call tools.
        """
        messages = state["messages"]
        
        # Prepare tools for the LLM
        available_tools = self.tools.to_openai_tools()
        
        user_id = state.get("user_id", "default_user")
        memory = self.get_memory_controller(user_id)
        
        # 1. Retrieve Semantic Context
        last_message = messages[-1].content if messages and isinstance(messages[-1], HumanMessage) else ""
        semantic_context = memory.retrieve_context(last_message) if last_message else ""
        
        # 2. Add System Prompt with Context
        system_prompt = f"""You are NaviBot Supervisor, an intelligent orchestrator.
        
Context from Memory:
{semantic_context}

Available Workers:
{json.dumps([w.dict() for w in role_manager.get_all_workers()], indent=2)}

Analyze the user's request. 
- If it requires a specialist (e.g. coding, research), call the worker by returning 'DELEGATE: <role_id>'.
- If you can answer directly or use general tools, do so.
"""
        
        litellm_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            if isinstance(msg, FunctionMessage):
                role = "function" # Or tool
                litellm_messages.append({"role": role, "name": msg.name, "content": msg.content})
            else:
                litellm_messages.append({"role": role, "content": msg.content})

        response = await self.llm.generate(
            messages=litellm_messages,
            tools=available_tools if available_tools else None
        )
        
        # Extract response content
        content = response.choices[0].message.content or ""
        tool_calls = response.choices[0].message.tool_calls

        new_messages = []
        next_step = "end"
        
        if tool_calls:
            next_step = "tools"
        elif content.startswith("DELEGATE:"):
            role_id = content.replace("DELEGATE:", "").strip()
            # Verify role exists
            if role_manager.get_worker(role_id):
                next_step = f"worker_{role_id}"
                new_messages.append(AIMessage(content=f"Delegating to {role_id}..."))
            else:
                new_messages.append(AIMessage(content=f"Error: Worker {role_id} not found."))
        elif content:
            new_messages.append(AIMessage(content=content))
        
        return {
            "messages": new_messages,
            "tool_calls": tool_calls,
            "next_step": next_step
        }

    async def tools_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the tools requested by the Supervisor.
        """
        tool_calls = state.get("tool_calls", [])
        results = []
        
        for call in tool_calls:
            function_name = call.function.name
            arguments = json.loads(call.function.arguments)
            
            try:
                output = await self.tools.execute(function_name, arguments)
                results.append(FunctionMessage(name=function_name, content=str(output)))
            except Exception as e:
                results.append(FunctionMessage(name=function_name, content=f"Error: {str(e)}"))

        return {"messages": results, "tool_calls": None}

    def should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Determine next node."""
        step = state.get("next_step")
        if step and (step == "tools" or step.startswith("worker_")):
            return step
        return "end"

# Initialize graph (singleton pattern or factory could be used)
# graph_app = AgentGraph(default_llm, registry)
