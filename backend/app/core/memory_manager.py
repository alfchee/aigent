
import os
import logging
from mem0 import Memory
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_memory_instance = None

class AgentMemory:
    def __init__(self):
        self.memory = None
        self._closed = False
        
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.warning("GOOGLE_API_KEY not found. Mem0 will not work correctly.")
                self._closed = True
                return

            # Configuration for Mem0 with Google GenAI
            # Using Qdrant for local vector storage
            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": os.getenv("NAVIBOT_MEMORY_DIR", "./navi_memory_qdrant"),
                        "embedding_model_dims": 768
                    }
                },
                "llm": {
                    "provider": "gemini",
                    "config": {
                        "model": "gemini-2.0-flash",
                        "api_key": api_key
                    }
                },
                "embedder": {
                    "provider": "gemini",
                    "config": {
                        "model": "models/gemini-embedding-001",
                        "api_key": api_key
                    }
                }
            }
            
            self.memory = Memory.from_config(config)
            logger.info("✅ Mem0 initialized successfully with Gemini.")
            
        except Exception as e:
            logger.error(f"⚠️  Failed to initialize Mem0: {e}")
            self._closed = True

    def add_interaction(self, user_id: str, text: str, metadata: dict = None):
        """
        Store a text snippet in memory (Mem0 extracts facts automatically).
        """
        if self._closed or self.memory is None:
            return False
            
        try:
            self.memory.add(text, user_id=user_id, metadata=metadata)
            logger.info(f"✅ Memory stored for user {user_id}: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"⚠️  Failed to add memory: {e}")
            return False

    def search_memory(self, user_id: str, query: str, n_results: int = 3) -> list[str]:
        """
        Search for relevant memories using semantic search.
        Returns a list of matching memory texts.
        """
        if self._closed or self.memory is None:
            return []
            
        try:
            results = self.memory.search(query, user_id=user_id, limit=n_results)
            # Mem0 returns dicts: {'results': [{'memory': '...', ...}]}
            if isinstance(results, dict) and 'results' in results:
                return [item['memory'] for item in results['results']]
            elif isinstance(results, list):
                return [item['memory'] for item in results]
            return []
            
        except Exception as e:
            logger.error(f"⚠️  Failed to search memory: {e}")
            return []

    def get_relevant_context(self, user_id: str, query: str) -> str:
        """
        Search for relevant memories using semantic search.
        Returns a formatted string for LLM context.
        """
        memories = self.search_memory(user_id, query, n_results=5)
        
        if not memories:
            return ""
        
        formatted = "\n".join([f"- {mem}" for mem in memories])
        return formatted

    def get_all_user_facts(self, user_id: str) -> list[str]:
        """
        Retrieve all stored memories for a user.
        """
        if self._closed or self.memory is None:
            return []
            
        try:
            results = self.memory.get_all(user_id=user_id)
            if isinstance(results, dict) and 'results' in results:
                return [item['memory'] for item in results['results']]
            elif isinstance(results, list):
                return [item['memory'] for item in results]
            return []
        except Exception as e:
            logger.error(f"⚠️  Failed to get all memories: {e}")
            return []

    def close(self):
        """
        Mem0 doesn't require explicit closing, but we maintain the interface.
        """
        self._closed = True
        logger.info("Memory system marked as closed.")

def get_agent_memory() -> AgentMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = AgentMemory()
    return _memory_instance

def cleanup_memory():
    """Global function to clean up memory resources on shutdown."""
    global _memory_instance
    if _memory_instance is not None:
        _memory_instance.close()
        _memory_instance = None
        print("Memory system cleaned up.")
