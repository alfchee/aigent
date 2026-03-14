"""
Semantic Memory Implementation

Provides long-term memory using Mem0 vector store for facts and knowledge.
This is the highest-level memory that persists user preferences,
facts, and other important information across sessions.
"""

from typing import List, Dict, Any, Optional
import logging

from .abc import MemoryBackend, MemoryItem

logger = logging.getLogger(__name__)


class SemanticMemory(MemoryBackend):
    """
    Semantic Memory: Facts and knowledge using vector store.
    
    Wraps the Mem0 implementation to provide semantic search
    capabilities. Stores facts, preferences, and important
    information that should persist across all sessions.
    """
    
    def __init__(self):
        """
        Initialize Semantic Memory.
        
        Uses the existing Mem0 implementation from memory_manager.
        """
        self._mem0 = None
        self._initialized = False
        logger.info("SemanticMemory initialized")
    
    def _ensure_initialized(self) -> bool:
        """
        Ensure Mem0 is initialized.
        
        Returns:
            True if Mem0 is available, False otherwise
        """
        if self._initialized:
            return self._mem0 is not None
        
        try:
            from app.core.memory_manager import get_agent_memory
            self._mem0 = get_agent_memory()
            self._initialized = True
            logger.debug("Mem0 wrapped successfully in SemanticMemory")
            return self._mem0 is not None
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            self._initialized = True
            self._mem0 = None
            return False
    
    async def add(self, item: MemoryItem) -> str:
        """
        Add a memory item to semantic memory (vector store).
        
        Args:
            item: The MemoryItem to store
            
        Returns:
            The ID of the stored item
        """
        if not self._ensure_initialized() or self._mem0 is None:
            logger.warning("Mem0 not available, skipping semantic memory add")
            return ""
        
        try:
            # Add to Mem0
            self._mem0.add_interaction(
                user_id=item.user_id,
                text=item.content,
                metadata=item.metadata
            )
            logger.debug(f"Added to semantic memory for user {item.user_id}")
            return item.id
            
        except Exception as e:
            logger.error(f"Failed to add to semantic memory: {e}")
            return ""
    
    async def search(
        self, 
        query: str, 
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None, 
        limit: int = 5
    ) -> List[MemoryItem]:
        """
        Search semantic memory for relevant facts.
        
        Uses vector similarity search to find relevant memories.
        
        Args:
            query: The search query text
            memory_type: Ignored for semantic memory
            user_id: User ID to search in
            limit: Maximum number of results
            
        Returns:
            List of relevant MemoryItems
        """
        if not self._ensure_initialized() or self._mem0 is None:
            logger.warning("Mem0 not available, skipping semantic memory search")
            return []
        
        if not user_id or not query:
            return []
        
        try:
            # Search using Mem0
            results = self._mem0.search_memory(
                user_id=user_id,
                query=query,
                n_results=limit
            )
            
            # Convert results to MemoryItems
            items = []
            for i, result in enumerate(results):
                # Handle different result formats
                if isinstance(result, dict):
                    content = result.get('memory', result.get('text', str(result)))
                else:
                    content = str(result)
                
                item = MemoryItem(
                    id=f"semantic_{i}",
                    content=content,
                    memory_type="semantic",
                    session_id="",  # Semantic memory is user-based, not session-based
                    user_id=user_id,
                    timestamp="",
                    metadata={}
                )
                items.append(item)
            
            logger.debug(f"Found {len(items)} semantic memories for user {user_id}")
            return items
            
        except Exception as e:
            logger.error(f"Failed to search semantic memory: {e}")
            return []
    
    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 100
    ) -> List[MemoryItem]:
        """
        Get all semantic memories for a user.
        
        Note: Semantic memory is user-based, not session-based.
        This returns all facts for the user (session_id acts as user_id).
        
        Args:
            session_id: User ID to get all facts for
            limit: Maximum number of items
            
        Returns:
            List of MemoryItems
        """
        return await self.get_all(session_id, limit)
    
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a semantic memory.
        
        Note: Mem0 handles deletion internally. This is a placeholder
        for future implementation.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            False (Mem0 doesn't expose direct deletion)
        """
        logger.warning("Semantic memory deletion not implemented in Mem0 wrapper")
        return False
    
    async def get_all(self, user_id: str, limit: int = 100) -> List[MemoryItem]:
        """
        Get all semantic memories for a user.
        
        Args:
            user_id: User ID to retrieve all memories for
            limit: Maximum number of items
            
        Returns:
            List of all MemoryItems for the user
        """
        if not self._ensure_initialized() or self._mem0 is None:
            logger.warning("Mem0 not available, skipping semantic memory get_all")
            return []
        
        if not user_id:
            return []
        
        try:
            # Get all memories using Mem0
            facts = self._mem0.get_all_user_facts(user_id)
            
            items = []
            for i, fact in enumerate(facts[:limit]):
                # Handle different fact formats
                if isinstance(fact, dict):
                    content = fact.get('memory', fact.get('text', str(fact)))
                else:
                    content = str(fact)
                
                item = MemoryItem(
                    id=f"semantic_{i}",
                    content=content,
                    memory_type="semantic",
                    session_id="",
                    user_id=user_id,
                    timestamp="",
                    metadata={}
                )
                items.append(item)
            
            logger.debug(f"Retrieved {len(items)} semantic memories for user {user_id}")
            return items
            
        except Exception as e:
            logger.error(f"Failed to get all semantic memories: {e}")
            return []
    
    def get_relevant_context(self, user_id: str, query: str, n_results: int = 5) -> str:
        """
        Synchronous method to get relevant context for LLM prompts.
        
        Args:
            user_id: User ID to search in
            query: Search query
            n_results: Number of results
            
        Returns:
            Formatted string of relevant facts
        """
        if not self._ensure_initialized() or self._mem0 is None:
            return ""
        
        try:
            return self._mem0.get_relevant_context(user_id, query)
        except Exception as e:
            logger.error(f"Failed to get relevant context: {e}")
            return ""


# Singleton instance
_semantic_memory_instance: Optional[SemanticMemory] = None


def get_semantic_memory() -> SemanticMemory:
    """
    Get the singleton SemanticMemory instance.
    
    Returns:
        The global SemanticMemory instance
    """
    global _semantic_memory_instance
    if _semantic_memory_instance is None:
        _semantic_memory_instance = SemanticMemory()
    return _semantic_memory_instance
