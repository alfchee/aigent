"""
Memory Skills Module

Provides skill functions for memory operations (recall_facts, save_fact).
This module wraps the new multi-level memory system.

These functions are exposed as tools to the agent.
"""

import re
from app.core.memory import get_memory_controller
from app.core.runtime_context import get_memory_user_id, is_scheduler_entity, get_entity_metadata


def recall_facts(query: str) -> str:
    """
    Searches for information in long-term memory (Semantic Memory).
    Useful when you need to remember past data, user preferences, details of previous projects
    or information not in the current conversation context.
    
    This uses the new multi-level memory system with vector store (Mem0).
    
    Args:
        query: The question or topic to search in memory.
        
    Returns:
        Formatted string with relevant facts or error message.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # DEBUG: Log what we get from context
    from app.core.runtime_context import get_memory_user_id, get_session_id
    debug_user_id = get_memory_user_id()
    debug_session_id = get_session_id()
    logger.info(f"[Memory DEBUG recall_facts] memory_user_id from context: {debug_user_id}, session_id: {debug_session_id}")
    
    # GHOST USER: Scheduler entities should not access human user memories
    if is_scheduler_entity():
        entity_meta = get_entity_metadata()
        parent_session = entity_meta.get('parent_session_id', 'unknown')
        return f"[Scheduler Task] Memory recall skipped for automated entity. Parent session: {parent_session}"
    
    memory_user_id = get_memory_user_id()
    if not memory_user_id:
        return "Error: Could not identify user for memory."
    
    logger.info(f"[Memory DEBUG recall_facts] Using memory_user_id: {memory_user_id}")
    
    import asyncio
    import concurrent.futures
    
    def _recall_sync():
        """Run recall in a separate thread with its own event loop."""
        import asyncio
        async def _recall():
            mc = get_memory_controller()
            results = await mc.search_memories(memory_user_id, query, limit=5)
            return results
        
        # Run in a new event loop in a separate thread
        return asyncio.run(_recall())
    
    try:
        # Use thread pool to run async code from sync context
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_recall_sync)
            results = future.result()  # Wait for result
            
            if not results:
                return "I found no relevant information in memory about that topic."
            
            formatted = "\n".join([f"- {r.content}" for r in results])
            return f"Information retrieved from memory:\n{formatted}"
            
    except Exception as e:
        logger.error(f"[Memory ERROR recall_facts] {str(e)}")
        return f"Error searching memory: {str(e)}"


def save_fact(fact: str) -> str:
    """
    Saves important information to long-term memory (Semantic Memory).
    Use it ONLY if the user gives you CRITICAL or NEW information that must be remembered in the future.
    Examples: names, preferences, important dates, project settings.
    DO NOT use for casual chat or temporary information.
    
    This uses the new multi-level memory system with vector store (Mem0).
    
    Args:
        fact: The fact or information to save.
        
    Returns:
        Success or error message.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # DEBUG: Log what we get from context
    from app.core.runtime_context import get_memory_user_id, get_session_id
    debug_user_id = get_memory_user_id()
    debug_session_id = get_session_id()
    logger.info(f"[Memory DEBUG save_fact] memory_user_id from context: {debug_user_id}, session_id: {debug_session_id}")
    
    # GHOST USER: Scheduler entities should not store to human user memories
    if is_scheduler_entity():
        entity_meta = get_entity_metadata()
        parent_session = entity_meta.get('parent_session_id', 'unknown')
        job_id = entity_meta.get('job_id', 'unknown')
        return f"[Scheduler Task] Memory save skipped for automated entity (Job: {job_id}). Parent session: {parent_session}"
    
    memory_user_id = get_memory_user_id()
    if not memory_user_id:
        return "Error: Could not identify user for memory."
    
    logger.info(f"[Memory DEBUG save_fact] Using memory_user_id: {memory_user_id}")
    
    text = (fact or "").strip()
    if not text:
        return "Error: Content is empty."
    
    if _looks_sensitive(text):
        return "I cannot store sensitive credentials or secrets in memory for security."
    
    import asyncio
    import concurrent.futures
    
    def _save_sync():
        """Run save in a separate thread with its own event loop."""
        import asyncio
        async def _save():
            mc = get_memory_controller()
            await mc.add_fact(memory_user_id, text, metadata={"source": "skill"})
        
        # Run in a new event loop in a separate thread
        asyncio.run(_save())
    
    try:
        # Use thread pool to run async code from sync context
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_save_sync)
            future.result()  # Wait for completion
            
        return "Memory updated successfully."
    except Exception as e:
        logger.error(f"[Memory ERROR save_fact] {str(e)}")
        return f"Error saving to memory: {str(e)}"


def _looks_sensitive(text: str) -> bool:
    """Check if text looks like sensitive credentials."""
    lowered = text.lower()
    keywords = [
        "password",
        "contraseña",
        "clave",
        "token",
        "api key",
        "apikey",
        "secret",
        "secreto",
    ]
    if any(k in lowered for k in keywords):
        return True
    if re.search(r"\b\d{4,}\b", text) and "clave" in lowered:
        return True
    return False


# Export tool names
search_memory_tool = recall_facts
save_memory_tool = save_fact

tools = [recall_facts, save_fact]
