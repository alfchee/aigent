from typing import Annotated, Dict, List, Literal, Optional, Sequence, TypedDict, Union, Any
import json
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, FunctionMessage
from app.core.llm import LLMService, ModelConfig
from app.skills.registry import ToolRegistry, registry

from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox

# Define the state of the graph
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], "messages"]
    next_step: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    user_id: Optional[str]
    session_id: Optional[str]

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

        # Set entry point
        self.workflow.set_entry_point("supervisor")

        # Add conditional edges
        self.workflow.add_conditional_edges(
            "supervisor",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )

        # Add edge from tools back to supervisor
        self.workflow.add_edge("tools", "supervisor")

        # Compile the graph
        self.app = self.workflow.compile()

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
        system_prompt = f"""You are NaviBot, an intelligent assistant.
        
Context from Memory:
{semantic_context}

Please assist the user based on the tools available.
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
        
        # Extract response content and tool calls
        content = response.choices[0].message.content
        tool_calls = response.choices[0].message.tool_calls

        new_messages = []
        if content:
            new_messages.append(AIMessage(content=content))
        
        # If tool calls are present, add them to state but don't execute yet
        # The tools_node will handle execution
        
        return {
            "messages": new_messages,
            "tool_calls": tool_calls,
            "next_step": "tools" if tool_calls else "end"
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
        """Determine if the graph should continue to tools or end."""
        if state.get("next_step") == "tools":
            return "continue"
        return "end"

# Initialize graph (singleton pattern or factory could be used)
# graph_app = AgentGraph(default_llm, registry)
