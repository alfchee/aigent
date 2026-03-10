"""
Conversation Summarizer Module for LangGraph

This module provides a summarizer node that compresses conversation history
when it exceeds a configurable threshold, using LLM to generate structured
summaries that preserve essential information.

Features:
- Configurable threshold (default: 10 messages)
- Compression levels (low, medium, high)
- Deduplication to avoid multiple summaries
- Idempotent operation
- Metadata tracking (tokens saved, messages compressed)
- Edge case handling
"""

import os
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """Compression levels affecting summary detail."""
    LOW = "low"      # Brief summary, keeps more context
    MEDIUM = "medium"  # Balanced summary
    HIGH = "high"    # Very compact, maximum compression


# Configuration
DEFAULT_MESSAGE_THRESHOLD = int(os.getenv("NAVIBOT_SUMMARIZER_THRESHOLD", "10"))
DEFAULT_COMPRESSION_LEVEL = os.getenv("NAVIBOT_SUMMARIZER_LEVEL", "medium")
DEFAULT_KEEP_RECENT_MESSAGES = int(os.getenv("NAVIBOT_SUMMARIZER_KEEP_RECENT", "3"))


@dataclass
class SummarizationMetadata:
    """Metadata about the summarization operation."""
    timestamp: str
    original_message_count: int
    compressed_message_count: int
    messages_removed: int
    tokens_saved_estimate: int
    compression_level: str
    was_summarized: bool = True


# Summary prompts based on compression level
SUMMARY_PROMPTS = {
    CompressionLevel.LOW: """Resumir la conversación de forma concisa preservando:
- Nombres de personas y entidades mencionadas
- Fechas y plazos importantes
- Decisiones tomadas
- Preferencias explícitas del usuario
- Tareas o acciones pendientes
- Archivos o recursos mencionados

Mantener un máximo de 5-7 oraciones.""",
    
    CompressionLevel.MEDIUM: """Resumir la conversación de forma breve preservando:
- Entidades clave (personas, lugares, productos)
- Decisiones importantes tomadas
- Preferencias del usuario
- Acciones realizadas
- Contexto mínimo necesario

Máximo 3-4 oraciones.""",
    
    CompressionLevel.HIGH: """Resumir la conversación de forma muy compacta:
- Solo información crítica: decisiones, fechas límite, preferencias principales
- Máximo 2 oraciones
- Formato: [Tema principal] - [Acción/Decisión] - [Próximo paso]"""
}


class ConversationSummarizer:
    """
    Manages conversation history summarization for LangGraph agents.
    """
    
    _instance: Optional['ConversationSummarizer'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._threshold = DEFAULT_MESSAGE_THRESHOLD
        self._compression_level = self._parse_compression_level(DEFAULT_COMPRESSION_LEVEL)
        self._keep_recent = DEFAULT_KEEP_RECENT_MESSAGES
        self._api_key = os.getenv("GOOGLE_API_KEY")
        self._summarizer_model = os.getenv("NAVIBOT_SUMMARIZER_MODEL", "gemini-1.5-flash-001")
        
        # Track recent summary hashes to avoid duplicate summaries
        self._recent_summary_hashes: Dict[str, str] = {}
        self._max_hash_cache_size = 100
        
        logger.info(
            f"ConversationSummarizer initialized: threshold={self._threshold}, "
            f"level={self._compression_level.value}, keep_recent={self._keep_recent}"
        )
    
    def _parse_compression_level(self, level: str) -> CompressionLevel:
        """Parse compression level from string."""
        try:
            return CompressionLevel(level.lower())
        except ValueError:
            logger.warning(f"Invalid compression level '{level}', defaulting to MEDIUM")
            return CompressionLevel.MEDIUM
    
    def configure(
        self,
        threshold: Optional[int] = None,
        compression_level: Optional[str] = None,
        keep_recent: Optional[int] = None
    ):
        """Configure the summarizer."""
        if threshold is not None:
            self._threshold = max(3, threshold)  # At least 3 messages
        if compression_level is not None:
            self._compression_level = self._parse_compression_level(compression_level)
        if keep_recent is not None:
            self._keep_recent = max(1, min(keep_recent, 10))  # Between 1-10
        
        logger.info(
            f"ConversationSummarizer configured: threshold={self._threshold}, "
            f"level={self._compression_level.value}, keep_recent={self._keep_recent}"
        )
    
    def _get_messages_hash(self, messages: List[Any]) -> str:
        """Generate hash of messages to detect duplicates."""
        content = ""
        for msg in messages:
            if hasattr(msg, 'content'):
                content += str(msg.content)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_summary_prompt(self) -> str:
        """Get the summary prompt based on compression level."""
        return SUMMARY_PROMPTS[self._compression_level]
    
    async def summarize(
        self,
        messages: List[Any],
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Summarize conversation history if it exceeds threshold.
        
        Args:
            messages: List of conversation messages
            session_id: Session identifier for deduplication
            
        Returns:
            Dictionary with:
            - messages: Updated message list (compressed or original)
            - summarization_metadata: Metadata about the operation (or None if not summarized)
        """
        # Edge case: empty or small history - no summarization needed
        if not messages or len(messages) <= self._threshold:
            logger.debug(f"Message count ({len(messages)}) below threshold ({self._threshold}), skipping summarization")
            return {
                "messages": messages,
                "summarization_metadata": None
            }
        
        # Check if we've already summarized this exact state (deduplication)
        current_hash = self._get_messages_hash(messages)
        session_hash_key = f"session_{session_id}"
        
        if session_hash_key in self._recent_summary_hashes:
            if self._recent_summary_hashes[session_hash_key] == current_hash:
                logger.debug("Same message state detected, skipping duplicate summarization")
                return {
                    "messages": messages,
                    "summarization_metadata": None
                }
        
        # Get recent messages to keep (context)
        recent_messages = messages[-self._keep_recent:] if len(messages) > self._keep_recent else messages
        messages_to_summarize = messages[:-self._keep_recent] if len(messages) > self._keep_recent else []
        
        if not messages_to_summarize:
            return {
                "messages": messages,
                "summarization_metadata": None
            }
        
        try:
            # Generate summary using LLM
            summary = await self._generate_summary(messages_to_summarize)
            
            if not summary:
                logger.warning("Summary generation returned empty, keeping original messages")
                return {
                    "messages": messages,
                    "summarization_metadata": None
                }
            
            # Create summary message with system role
            from langchain_core.messages import SystemMessage
            
            summary_message = SystemMessage(
                content=f"📝 **RESUMEN DE CONVERSACIÓN ANTERIOR**\n\n{summary}\n\n---\n*Resumen generado automáticamente. Consulta este resumen para contexto histórico.*"
            )
            
            # Combine summary with recent messages
            new_messages = [summary_message] + recent_messages
            
            # Estimate tokens saved (rough: ~4 chars per token)
            original_chars = sum(len(getattr(m, 'content', '')) for m in messages)
            new_chars = sum(len(getattr(m, 'content', '')) for m in new_messages)
            tokens_saved = max(0, (original_chars - new_chars) // 4)
            
            # Create metadata
            metadata = SummarizationMetadata(
                timestamp=datetime.now().isoformat(),
                original_message_count=len(messages),
                compressed_message_count=len(new_messages),
                messages_removed=len(messages) - len(new_messages),
                tokens_saved_estimate=tokens_saved,
                compression_level=self._compression_level.value,
                was_summarized=True
            )
            
            # Update hash cache for deduplication
            self._recent_summary_hashes[session_hash_key] = current_hash
            if len(self._recent_summary_hashes) > self._max_hash_cache_size:
                # Remove oldest entries
                keys_to_remove = list(self._recent_summary_hashes.keys())[:-self._max_hash_cache_size//2]
                for key in keys_to_remove:
                    del self._recent_summary_hashes[key]
            
            logger.info(
                f"Summarized {len(messages)} messages to {len(new_messages)} "
                f"(saved ~{tokens_saved} tokens)"
            )
            
            return {
                "messages": new_messages,
                "summarization_metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error during summarization: {e}", exc_info=True)
            # On error, return original messages
            return {
                "messages": messages,
                "summarization_metadata": None
            }
    
    async def _generate_summary(self, messages: List[Any]) -> str:
        """Generate summary using LLM."""
        from google import genai
        from google.genai import types
        
        if not self._api_key:
            logger.warning("No GOOGLE_API_KEY, using fallback text-based summary")
            return self._fallback_summary(messages)
        
        client = genai.Client(api_key=self._api_key)
        
        # Build conversation context
        conversation_text = ""
        for msg in messages:
            role = getattr(msg, 'role', 'unknown')
            content = getattr(msg, 'content', '')
            if content:
                conversation_text += f"\n{role.upper()}: {content}"
        
        prompt = f"""Eres un asistente que resume conversaciones de manera eficiente.

Conversación a resumir:
{conversation_text}

{self._get_summary_prompt()}

Responde ÚNICAMENTE con el resumen, sin introducciones ni conclusiones."""

        try:
            response = client.models.generate_content(
                model=self._summarizer_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=500
                )
            )
            
            if response and response.text:
                return response.text.strip()
            return ""
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return self._fallback_summary(messages)
    
    def _fallback_summary(self, messages: List[Any]) -> str:
        """Simple fallback summary when LLM is unavailable."""
        if not messages:
            return "Sin mensajes anteriores."
        
        # Extract key information simply
        user_messages = [m for m in messages if getattr(m, 'role', '') == 'user']
        last_user = user_messages[-1].content if user_messages else ""
        
        return f"Conversación anterior con {len(messages)} mensajes. Último mensaje del usuario: {last_user[:100]}..."


# Singleton accessor
def get_summarizer() -> ConversationSummarizer:
    """Get the singleton ConversationSummarizer instance."""
    return ConversationSummarizer()


# Convenience function for node
async def node_summarizer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that summarizes conversation history when needed.
    
    This node should be inserted as a checkpoint before processing nodes
    that handle extensive history.
    
    Args:
        state: Agent state containing messages
        
    Returns:
        Updated state with compressed messages and metadata
    """
    messages = state.get("messages", [])
    session_id = state.get("session_id", "default")
    
    summarizer = get_summarizer()
    
    result = await summarizer.summarize(messages, session_id)
    
    return {
        "messages": result["messages"],
        "summarization_metadata": result.get("summarization_metadata")
    }


# Export for easy import
__all__ = [
    "ConversationSummarizer",
    "node_summarizer",
    "get_summarizer",
    "CompressionLevel",
    "SummarizationMetadata",
    "DEFAULT_MESSAGE_THRESHOLD",
    "DEFAULT_COMPRESSION_LEVEL"
]
