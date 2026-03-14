"""
Memory Module - Multi-Level Memory Architecture

This module provides a provider-agnostic multi-level memory system:
- Working Memory: Immediate attention window (in-memory)
- Episodic Memory: Session history (SQLite persistence)
- Semantic Memory: Facts and knowledge (Mem0 vector store)
- Global Context: Cross-session preferences
"""

from .abc import MemoryBackend, MemoryItem
from .working import WorkingMemory, get_working_memory
from .episodic import EpisodicMemory, get_episodic_memory
from .semantic import SemanticMemory, get_semantic_memory
from .controller import MemoryController, MemoryContext, get_memory_controller

__all__ = [
    "MemoryBackend",
    "MemoryItem", 
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "MemoryController",
    "MemoryContext",
    "get_working_memory",
    "get_episodic_memory",
    "get_semantic_memory",
    "get_memory_controller",
]
