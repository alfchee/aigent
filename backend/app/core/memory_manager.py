import os
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import time
import uuid

load_dotenv()

_memory_instance = None

class LocalEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Wrapper for sentence-transformers to work with ChromaDB.
    Avoids using external APIs and gives us full control.
    """
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight model optimized for semantic search
            self.model_name = 'all-MiniLM-L6-v2'
            self.model = SentenceTransformer(self.model_name)
            print(f"✅ Local embedding model loaded: {self.model_name}")
        except ImportError:
            print("❌ sentence-transformers not found. Please install it.")
            raise
        except Exception as e:
            print(f"❌ Failed to load embedding model: {e}")
            raise

    def __call__(self, input):
        # Handle both string and list of strings
        if isinstance(input, str):
            input = [input]
        embeddings = self.model.encode(input)
        # Convert numpy array to list for ChromaDB
        return embeddings.tolist()

    def name(self):
        return "local_sentence_transformer"

class AgentMemory:
    def __init__(self):
        self.client = None
        self.collection = None
        self._closed = False
        
        try:
            # Initialize embedding function
            self.ef = LocalEmbeddingFunction()
            
            # Configure ChromaDB
            db_path = os.getenv("NAVIBOT_MEMORY_DIR", "./navi_memory_db")
            
            # Use PersistentClient for disk storage
            # Settings: anonymized_telemetry=False to avoid network calls
            # Critical: Ensure persist_directory matches and IS ABSOLUTE if possible to avoid relative path confusion
            db_path = os.path.abspath(db_path)
            
            self.client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="navibot_memory",
                embedding_function=self.ef,
                metadata={"hnsw:space": "cosine"} # Cosine similarity for semantic search
            )
            
            print(f"✅ ChromaDB initialized at {db_path}")
            
        except Exception as e:
            print(f"⚠️  Warning: Failed to initialize ChromaDB: {e}")
            import traceback
            traceback.print_exc()
            self._closed = True

    def add_interaction(self, user_id: str, text: str):
        """
        Store a text snippet in memory.
        Since we removed mem0's LLM extraction, we store the raw text directly.
        Future improvement: Use LLM to extract facts before storing if needed.
        """
        if self._closed or self.collection is None:
            return False
            
        try:
            # Generate a unique ID
            mem_id = str(uuid.uuid4())
            timestamp = str(time.time())
            
            self.collection.add(
                documents=[text],
                metadatas=[{"user_id": user_id, "timestamp": timestamp, "type": "fact"}],
                ids=[mem_id]
            )
            print(f"✅ Memory stored for user {user_id}: {text[:50]}...")
            return True
        except Exception as e:
            print(f"⚠️  Failed to add memory: {e}")
            return False

    def get_relevant_context(self, user_id: str, query: str) -> str:
        """
        Search for relevant memories using semantic search.
        """
        if self._closed or self.collection is None:
            return ""
            
        try:
            # Query ChromaDB
            # We filter by user_id to ensure privacy/separation
            results = self.collection.query(
                query_texts=[query],
                n_results=3,
                where={"user_id": user_id}
            )
            
            # ChromaDB returns lists of lists (one list per query)
            documents = results['documents'][0] if results['documents'] else []
            
            if not documents:
                return ""
            
            formatted = "\n".join([f"- {doc}" for doc in documents])
            return formatted
            
        except Exception as e:
            print(f"⚠️  Failed to search memory: {e}")
            return ""

    def get_all_user_facts(self, user_id: str):
        """
        Retrieve all stored memories for a user.
        """
        if self._closed or self.collection is None:
            return []
            
        try:
            # ChromaDB get() allows filtering
            results = self.collection.get(
                where={"user_id": user_id}
            )
            return results['documents'] if results['documents'] else []
        except Exception as e:
            print(f"⚠️  Failed to get all memories: {e}")
            return []

    def close(self):
        """
        ChromaDB client doesn't need explicit closing in newer versions,
        but we mark as closed to stop operations.
        """
        self._closed = True
        print("Memory system marked as closed.")

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
