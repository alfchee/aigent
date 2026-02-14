import asyncio
import functools
from app.core.runtime_context import get_session_id
from app.core.persistence import save_tool_call

def wrap_tool(tool):
    if getattr(tool, "_navibot_wrapped", False):
        return tool
    is_async = asyncio.iscoroutinefunction(tool)

    if is_async:
        @functools.wraps(tool)
        async def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                result = await tool(*args, **kwargs)
                save_tool_call(session_id, tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.__name__, args, kwargs, None, str(e))
                raise
    else:
        @functools.wraps(tool)
        def wrapped(*args, **kwargs):
            session_id = get_session_id()
            try:
                result = tool(*args, **kwargs)
                save_tool_call(session_id, tool.__name__, args, kwargs, result, None)
                return result
            except Exception as e:
                save_tool_call(session_id, tool.__name__, args, kwargs, None, str(e))
                raise

    wrapped._navibot_wrapped = True
    
    # Preserve signature if present on original tool (important for patched signatures)
    if hasattr(tool, "__signature__"):
        wrapped.__signature__ = tool.__signature__
        
    return wrapped
