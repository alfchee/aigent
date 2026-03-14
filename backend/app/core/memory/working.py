"""
Working Memory Implementation

Provides ephemeral in-memory storage for immediate conversation context.
Implements a sliding window of recent messages for the attention mechanism.
"""

from typing import List, Dict, Optional
import time
import uuid
import logging

from .abc import MemoryBackend, MemoryItem

logger = logging.getLogger(__name__)


class WorkingMemory(MemoryBackend):
    """
    Working Memory: Immediate attention window.
    
    Stores the immediate conversation context in memory with a sliding
    window mechanism (FIFO). This is the fastest access memory but
    is ephemeral - data is lost on restart.
    
    Configuration:
        max_tokens: Approximate max tokens (used for limiting)
        max_items: Maximum number of items to keep per session
    """
    
    def __init__(self, max_tokens: int = 4000, max_items: int = 20):
        """
        Initialize Working Memory.
        
        Args:
            max_tokens: Approximate token limit (for future implementation)
            max_items: Maximum number of conversation turns to keep
        """
        self.max_tokens = max_tokens
        self.max_items = max_items
        # session_id -> list of MemoryItems
        self._cache: Dict[str, List[MemoryItem]] = {}
        logger.info(f"WorkingMemory initialized with max_items={max_items}")
    
    async def add(self, item: MemoryItem) -> str:
        """
        Add a memory item to working memory.
        
        Uses FIFO eviction - when max_items is reached, oldest items
        are removed first.
        
        Args:
            item: The MemoryItem to add
            
        Returns:
            The ID of the stored item
        """
        # Initialize session cache if needed
        if item.session_id not in self._cache:
            self._cache[item.session_id] = []
        
        # Generate unique ID if not provided
        if not item.id:
            item.id = str(uuid.uuid4())
        
        # Set timestamp
        item.timestamp = str(time.time())
        item.memory_type = "working"
        
        # FIFO eviction: remove oldest items if at capacity
        cache = self._cache[item.session_id]
        while len(cache) >= self.max_items:
            evicted = cache.pop(0)
            logger.debug(f"Evicted oldest item from working memory: {evicted.id}")
        
        # Add new item
        cache.append(item)
        logger.debug(f"Added item to working memory: {item.id}")
        
        return item.id
    
    async def search(
        self, 
        query: str, 
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None, 
        limit: int = 5
    ) -> List[MemoryItem]:
        """
        Search working memory.
        
        Note: Working memory doesn't perform semantic search.
        Returns the most recent items instead (simple retrieval).
        
        Args:
            query: Ignored for working memory
            memory_type: Optional filter (ignored, always returns working)
            user_id: Session ID to search in (uses session_id internally)
            limit: Maximum number of items to return
            
        Returns:
            List of most recent MemoryItems
        """
        # For working memory, user_id acts as session_id
        session_id = user_id or ""
        
        if not session_id or session_id not in self._cache:
            return []
        
        # Return most recent items
        items = self._cache[session_id]
        return items[-limit:] if len(items) > limit else items
    
    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 100
    ) -> List[MemoryItem]:
        """
        Get all items for a specific session.
        
        Args:
            session_id: The session ID to retrieve history for
            limit: Maximum number of items to return
            
        Returns:
            List of MemoryItems for the session (most recent last)
        """
        if session_id not in self._cache:
            return []
        
        items = self._cache[session_id]
        if limit >= len(items):
            return items.copy()
        
        # Return most recent 'limit' items
        return items[-limit:]
    
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a specific item from working memory.
        
        Args:
            memory_id: The ID of the item to delete
            
        Returns:
            True if item was found and deleted, False otherwise
        """
        for session_items in self._cache.values():
            for i, item in enumerate(session_items):
                if item.id == memory_id:
                    session_items.pop(i)
                    logger.debug(f"Deleted item from working memory: {memory_id}")
                    return True
        
        return False
    
    async def get_all(self, user_id: str, limit: int = 100) -> List[MemoryItem]:
        """
        Get all working memory items for a user.
        
        For working memory, user_id maps to session_id.
        
        Args:
            user_id: Session ID to get all items for
            limit: Maximum number of items to return
            
        Returns:
            List of all MemoryItems for the session
        """
        return await self.get_session_history(user_id, limit)
    
    def get_context_window(self, session_id: str, max_items: int = 10) -> str:
        """
        Get the current context window formatted for LLM prompts.
        
        Returns a formatted string of recent conversation turns
        suitable for injection into an LLM prompt.
        
        Args:
            session_id: The session ID to get context for
            max_items: Maximum number of recent items to include
            
        Returns:
            Formatted string with role: content pairs
        """
        if session_id not in self._cache:
            return ""
        
        items = self._cache[session_id]
        # Get the most recent items
        recent_items = items[-max_items:] if len(items) > max_items else items
        
        if not recent_items:
            return ""
        
        # Format as conversation
        formatted_parts = []
        for item in recent_items:
            role = item.metadata.get("role", "user")
            formatted_parts.append(f"{role}: {item.content}")
        
        return "\n".join(formatted_parts)
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear all working memory for a specific session.
        
        Args:
            session_id: The session ID to clear
        """
        if session_id in self._cache:
            self._cache[session_id] = []
            logger.info(f"Cleared working memory for session: {session_id}")
    
    def get_session_count(self, session_id: str) -> int:
        """
        Get the number of items in a session's working memory.
        
        Args:
            session_id: The session ID to check
            
        Returns:
            Number of items in memory for this session
        """
        return len(self._cache.get(session_id, []))


# Singleton instance for the application
_working_memory_instance: Optional[WorkingMemory] = None


def get_working_memory() -> WorkingMemory:
    """
    Get the singleton WorkingMemory instance.
    
    Returns:
        The global WorkingMemory instance
    """
    global _working_memory_instance
    if _working_memory_instance is None:
        _working_memory_instance = WorkingMemory()
    return _working_memory_instance
