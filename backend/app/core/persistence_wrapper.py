import asyncio
import functools
import inspect
from app.core.runtime_context import get_session_id
from app.core.persistence import save_tool_call

def wrap_tool(tool):
    if getattr(tool, "_navibot_wrapped", False):
        return tool
    
    # Determine if it's a LangChain StructuredTool and extract metadata source
    metadata_source = tool
    is_async = asyncio.iscoroutinefunction(tool)
    is_structured_tool = hasattr(tool, "args_schema") and (hasattr(tool, "func") or hasattr(tool, "coroutine"))
    
    if is_structured_tool:
        if hasattr(tool, "coroutine") and tool.coroutine:
            metadata_source = tool.coroutine
            is_async = True
        elif hasattr(tool, "func") and tool.func:
            metadata_source = tool.func
            if asyncio.iscoroutinefunction(metadata_source):
                is_async = True

    if is_async:
        @functools.wraps(metadata_source)
        async def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                if is_structured_tool and hasattr(tool, "arun"):
                    # Use arun for async StructuredTools
                    # Convert args/kwargs to dict using signature to support positional args
                    sig = inspect.signature(metadata_source)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    tool_input = bound.arguments
                    result = await tool.arun(tool_input)
                else:
                    result = await tool(*args, **kwargs)
                
                save_tool_call(session_id, tool.name if is_structured_tool else tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.name if is_structured_tool else tool.__name__, args, kwargs, None, str(e))
                raise
    else:
        @functools.wraps(metadata_source)
        def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                if is_structured_tool and hasattr(tool, "run"):
                     # Use run for sync StructuredTools
                     # Convert args/kwargs to dict using signature to support positional args
                     sig = inspect.signature(metadata_source)
                     bound = sig.bind(*args, **kwargs)
                     bound.apply_defaults()
                     tool_input = bound.arguments
                     result = tool.run(tool_input)
                else:
                    result = tool(*args, **kwargs)
                
                save_tool_call(session_id, tool.name if is_structured_tool else tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.name if is_structured_tool else tool.__name__, args, kwargs, None, str(e))
                raise

    wrapped._navibot_wrapped = True
    
    # Preserve signature if present on original tool (important for patched signatures)
    if hasattr(metadata_source, "__signature__"):
        wrapped.__signature__ = metadata_source.__signature__
        
    return wrapped
