"""
Abstract Base Classes for Memory Backends

Provides a provider-agnostic interface for multi-level memory system.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class MemoryItem:
    """
    Individual memory element representing a single piece of information
    stored in any level of the memory system.
    
    Attributes:
        id: Unique identifier for this memory item
        content: The actual text content of the memory
        memory_type: Type of memory - "working" | "episodic" | "semantic" | "global"
        session_id: Associated session ID (for working/episodic memory)
        user_id: Associated user ID
        timestamp: ISO timestamp when the memory was created
        metadata: Additional key-value data for this memory
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: str = "working"  # working | episodic | semantic | global
    session_id: str = ""
    user_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert MemoryItem to dictionary representation."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class MemoryBackend(ABC):
    """
    Abstract interface for memory backends.
    
    All memory implementations (working, episodic, semantic) must inherit
    from this class and implement all abstract methods.
    This provides a provider-agnostic interface for the memory system.
    """
    
    @abstractmethod
    async def add(self, item: MemoryItem) -> str:
        """
        Add a memory item to the backend.
        
        Args:
            item: The MemoryItem to store
            
        Returns:
            The ID of the stored memory item
        """
        pass
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None, 
        limit: int = 5
    ) -> List[MemoryItem]:
        """
        Search for memory items matching a query.
        
        Args:
            query: The search query text
            memory_type: Optional filter by memory type
            user_id: Optional filter by user ID
            limit: Maximum number of results to return
            
        Returns:
            List of matching MemoryItem objects
        """
        pass
    
    @abstractmethod
    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 100
    ) -> List[MemoryItem]:
        """
        Get all memory items for a specific session.
        
        Args:
            session_id: The session ID to retrieve history for
            limit: Maximum number of items to return
            
        Returns:
            List of MemoryItem objects in chronological order
        """
        pass
    
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory item by its ID.
        
        Args:
            memory_id: The ID of the memory item to delete
            
        Returns:
            True if the item was deleted, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_all(self, user_id: str, limit: int = 100) -> List[MemoryItem]:
        """
        Get all memory items for a user across all sessions.
        
        Args:
            user_id: The user ID to retrieve all memories for
            limit: Maximum number of items to return
            
        Returns:
            List of MemoryItem objects
        """
        pass


class WorkingMemoryBackend(ABC):
    """
    Specialized interface for working memory (immediate context window).
    
    Working memory is ephemeral and stores the immediate conversation context.
    """
    
    @abstractmethod
    def get_context_window(self, session_id: str, max_items: int = 10) -> str:
        """
        Get the current context window formatted for LLM prompt injection.
        
        Args:
            session_id: The session ID to get context for
            max_items: Maximum number of recent items to include
            
        Returns:
            Formatted string representation of the context window
        """
        pass
    
    @abstractmethod
    def clear_session(self, session_id: str) -> None:
        """
        Clear all working memory for a specific session.
        
        Args:
            session_id: The session ID to clear
        """
        pass
