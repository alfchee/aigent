"""
Memory Controller - Unified Memory Management

Provides a unified interface for managing all 4 levels of memory:
- Working Memory: Immediate context window
- Episodic Memory: Session history (SQLite)
- Semantic Memory: Facts and knowledge (Mem0)
- Global Context: Cross-session preferences

This controller is provider-agnostic and works with any LLM provider.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import logging
import uuid

from .abc import MemoryItem
from .working import WorkingMemory, get_working_memory
from .episodic import EpisodicMemory, get_episodic_memory
from .semantic import SemanticMemory, get_semantic_memory

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """
    Consolidated context from all memory levels.
    
    This dataclass holds the formatted context from all 4 memory levels
    that can be injected into LLM prompts.
    
    Attributes:
        working_memory: Formatted immediate conversation context
        episodic_summary: Summary of previous sessions
        semantic_facts: Relevant facts from vector store
        global_preferences: User preferences across sessions
    """
    working_memory: str = ""
    episodic_summary: str = ""
    semantic_facts: str = ""
    global_preferences: str = ""
    
    def to_prompt_format(self) -> str:
        """
        Convert all context to LLM prompt format.
        
        Returns:
            Formatted string with all context sections
        """
        parts = []
        
        if self.global_preferences:
            parts.append(f"## Preferencias del Usuario\n{self.global_preferences}")
        
        if self.semantic_facts:
            parts.append(f"## Hechos Recordados\n{self.semantic_facts}")
        
        if self.episodic_summary:
            parts.append(f"## Contexto de Sesiones Anteriores\n{self.episodic_summary}")
        
        if self.working_memory:
            parts.append(f"## Conversación Actual\n{self.working_memory}")
        
        return "\n\n".join(parts) if parts else ""
    
    def is_empty(self) -> bool:
        """Check if all context is empty."""
        return not any([
            self.working_memory,
            self.episodic_summary,
            self.semantic_facts,
            self.global_preferences
        ])


class MemoryController:
    """
    Unified Memory Controller - Provider Agnostic.
    
    Manages all 4 levels of memory transparently, providing a single
    interface for the agent to interact with memory.
    
    This controller abstracts away the underlying memory implementations
    and provides a unified API for adding messages, facts, and retrieving
    context for LLM prompts.
    """
    
    _instance: Optional["MemoryController"] = None
    
    def __init__(self):
        """Initialize the memory controller with all memory backends."""
        # Initialize all memory levels
        self.working = get_working_memory()
        self.episodic = get_episodic_memory()
        self.semantic = get_semantic_memory()
        
        # Global preferences cache (user_id -> preferences string)
        self._global_cache: Dict[str, str] = {}
        
        # Session tracking
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("MemoryController initialized with all memory levels")
    
    @classmethod
    def get_singleton(cls) -> "MemoryController":
        """
        Get the singleton instance of MemoryController.
        
        Returns:
            The global MemoryController instance
        """
        if cls._instance is None:
            cls._instance = cls()
            logger.info("MemoryController singleton created")
        return cls._instance
    
    # =========================================================================
    # Message/Conversation Management
    # =========================================================================
    
    async def add_message(
        self, 
        session_id: str, 
        user_id: str, 
        role: str, 
        content: str
    ) -> str:
        """
        Add a message to working memory and persist to episodic memory.
        
        This is the main method for storing conversation messages.
        The message is stored in both working memory (immediate context)
        and episodic memory (persistent history).
        
        Args:
            session_id: The session ID
            user_id: The user ID
            role: Message role (user, assistant, model)
            content: The message content
            
        Returns:
            The ID of the stored memory item
        """
        item = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            memory_type="working",
            session_id=session_id,
            user_id=user_id,
            timestamp="",
            metadata={"role": role}
        )
        
        # Add to working memory (immediate context)
        await self.working.add(item)
        
        # Also persist to episodic memory (persistent history)
        item.memory_type = "episodic"
        episodic_id = await self.episodic.add(item)
        
        logger.debug(f"Added message to memory: session={session_id}, role={role}")
        return episodic_id or item.id
    
    async def add_conversation_turn(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_message: str
    ) -> None:
        """
        Add a complete conversation turn (user + assistant).
        
        Convenience method for adding both sides of a conversation.
        
        Args:
            session_id: The session ID
            user_id: The user ID
            user_message: The user's message
            assistant_message: The assistant's response
        """
        await self.add_message(session_id, user_id, "user", user_message)
        await self.add_message(session_id, user_id, "assistant", assistant_message)
    
    # =========================================================================
    # Fact/knowledge Management
    # =========================================================================
    
    async def add_fact(
        self, 
        user_id: str, 
        fact: str, 
        metadata: Dict = None
    ) -> str:
        """
        Add a fact to semantic memory.
        
        Facts are stored in the vector store for semantic search.
        
        Args:
            user_id: The user ID
            fact: The fact to store
            metadata: Optional metadata
            
        Returns:
            The ID of the stored fact
        """
        item = MemoryItem(
            id=str(uuid.uuid4()),
            content=fact,
            memory_type="semantic",
            session_id="",  # Semantic memory is user-based
            user_id=user_id,
            timestamp="",
            metadata=metadata or {}
        )
        
        return await self.semantic.add(item)
    
    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[MemoryItem]:
        """
        Search semantic memory for relevant facts.
        
        Args:
            user_id: The user ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of relevant MemoryItems
        """
        return await self.semantic.search(
            query=query,
            user_id=user_id,
            limit=limit
        )
    
    # =========================================================================
    # Context Retrieval
    # =========================================================================
    
    async def get_context(
        self,
        session_id: str,
        user_id: str,
        current_query: str = ""
    ) -> MemoryContext:
        """
        Get consolidated context from all memory levels.
        
        This is the main method for retrieving context to inject into
        LLM prompts. It aggregates context from all 4 memory levels.
        
        Args:
            session_id: Current session ID
            user_id: User ID
            current_query: Current user message (for semantic search)
            
        Returns:
            MemoryContext with all context sections
        """
        # 1. Working memory: recent conversation context
        working = self.working.get_context_window(session_id, max_items=10)
        
        # 2. Episodic: Get session history for context
        episodic = ""
        if current_query:
            # If there's a current query, get relevant episodic context
            episodic_history = await self.episodic.get_session_history(
                session_id, limit=10
            )
            # Format recent history
            if episodic_history:
                episodic_parts = []
                for item in episodic_history[-5:]:
                    role = item.metadata.get("role", "user")
                    episodic_parts.append(f"{role}: {item.content[:200]}")
                episodic = "\n".join(episodic_parts)
        
        # 3. Semantic: Facts relevant to current query
        semantic = ""
        if current_query:
            semantic_results = await self.semantic.search(
                query=current_query,
                user_id=user_id,
                limit=5
            )
            if semantic_results:
                semantic = "\n".join([f"- {r.content}" for r in semantic_results])
        
        # 4. Global: User preferences
        global_pref = self._global_cache.get(user_id, "")
        
        return MemoryContext(
            working_memory=working,
            episodic_summary=episodic,
            semantic_facts=semantic,
            global_preferences=global_pref
        )
    
    # =========================================================================
    # Global Preferences
    # =========================================================================
    
    async def set_user_preference(
        self, 
        user_id: str, 
        preference: str
    ) -> None:
        """
        Save a global user preference.
        
        Preferences are cached in memory and can be retrieved
        across sessions.
        
        Args:
            user_id: The user ID
            preference: The preference to store
        """
        current = self._global_cache.get(user_id, "")
        if current:
            self._global_cache[user_id] = f"{current}\n{preference}".strip()
        else:
            self._global_cache[user_id] = preference
        
        logger.debug(f"Set user preference for {user_id}")
    
    async def get_user_preferences(self, user_id: str) -> str:
        """
        Get all user preferences.
        
        Args:
            user_id: The user ID
            
        Returns:
            Formatted preferences string
        """
        return self._global_cache.get(user_id, "")
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear working memory for a session.
        
        Note: This only clears working memory. Episodic and semantic
        memory are persistent and not affected.
        
        Args:
            session_id: The session ID to clear
        """
        self.working.clear_session(session_id)
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
        logger.info(f"Cleared session memory: {session_id}")
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[MemoryItem]:
        """
        Get full session history from episodic memory.
        
        Args:
            session_id: The session ID
            limit: Maximum messages to retrieve
            
        Returns:
            List of MemoryItems
        """
        return await self.episodic.get_session_history(session_id, limit)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_memory_stats(self, session_id: str = None) -> Dict[str, Any]:
        """
        Get memory statistics.
        
        Args:
            session_id: Optional session ID for working memory stats
            
        Returns:
            Dictionary with memory statistics
        """
        stats = {
            "working_memory": {},
            "global_preferences": len(self._global_cache)
        }
        
        if session_id:
            stats["working_memory"] = {
                "session_id": session_id,
                "item_count": self.working.get_session_count(session_id)
            }
        
        return stats


# Singleton accessor function
def get_memory_controller() -> MemoryController:
    """
    Get the singleton MemoryController instance.
    
    Returns:
        The global MemoryController
    """
    return MemoryController.get_singleton()
