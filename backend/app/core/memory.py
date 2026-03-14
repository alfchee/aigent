"""
Legacy Memory Module - DEPRECATED

This module is deprecated. Please use the new multi-level memory system:

    from app.core.memory import get_memory_controller
    
    mc = get_memory_controller()
    await mc.add_fact(user_id, "fact to remember")
    context = await mc.get_context(session_id, user_id, "query")

This file is kept for backward compatibility only.
"""

import warnings
from typing import List

# Emit deprecation warning
warnings.warn(
    "app.core.memory is deprecated. Use app.core.memory instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new memory module for backward compatibility
from app.core.memory import get_memory_controller

def save_memory(user_id: str, text: str, source: str) -> None:
    """
    DEPRECATED: Use MemoryController.add_fact() instead.
    
    Saves a piece of information to semantic memory.
    
    Args:
        user_id: User identifier
        text: Text to remember
        source: Origin of the data
    """
    import asyncio
    
    async def _save():
        mc = get_memory_controller()
        await mc.add_fact(user_id, text, metadata={"source": source})
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use run_until_complete in async context
            # Just create a task
            import asyncio
            asyncio.create_task(_save())
        else:
            loop.run_until_complete(_save())
    except Exception:
        pass  # Silently fail for backward compatibility

def recall_memory(user_id: str, query: str, n_results: int = 3) -> List[str]:
    """
    DEPRECATED: Use MemoryController.get_context() instead.
    
    Retrieves relevant information from semantic memory.
    
    Args:
        user_id: User identifier
        query: Search query
        n_results: Number of results
        
    Returns:
        List of relevant memory texts
    """
    import asyncio
    
    async def _recall():
        mc = get_memory_controller()
        results = await mc.search_memories(user_id, query, n_results)
        return [r.content for r in results]
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return []
        else:
            return loop.run_until_complete(_recall())
    except Exception:
        return []
