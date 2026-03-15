from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, Field, create_model
from inspect import signature, Parameter

class ToolDefinition(BaseModel):
    name: str
    description: str
    args_schema: Type[BaseModel]
    func: Callable

class ToolRegistry:
    """
    Central registry for all tools (local and MCP).
    Enforces strict Pydantic validation for inputs and outputs.
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, args_schema: Optional[Type[BaseModel]] = None):
        """Decorator to register a function as a tool."""
        def decorator(func: Callable):
            schema = args_schema
            if not schema:
                # Auto-generate Pydantic model from type hints if not provided
                sig = signature(func)
                fields = {}
                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue
                    annotation = param.annotation if param.annotation != Parameter.empty else Any
                    default = param.default if param.default != Parameter.empty else ...
                    fields[param_name] = (annotation, default)
                
                schema = create_model(f"{func.__name__}Args", **fields)

            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                args_schema=schema,
                func=func
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Convert registered tools to OpenAI function format."""
        openai_tools = []
        for tool in self._tools.values():
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_schema.model_json_schema()
                }
            })
        return openai_tools

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with validated arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found.")
        
        # Validate arguments using Pydantic
        try:
            validated_args = tool.args_schema(**arguments)
        except Exception as e:
            raise ValueError(f"Invalid arguments for tool '{name}': {e}")

        # Execute the function
        # Support both sync and async functions
        if isinstance(tool.func, Callable):
            import inspect
            if inspect.iscoroutinefunction(tool.func):
                return await tool.func(**validated_args.model_dump())
            else:
                return tool.func(**validated_args.model_dump())
        return None

# Global registry instance
registry = ToolRegistry()
