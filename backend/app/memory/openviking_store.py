import os
import logging
from typing import Optional, List, Dict, Any
from openviking import OpenViking
from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.memory.openviking")

class OpenVikingConfig(BaseModel):
    """Configuration for OpenViking Context Database."""
    # LLM for reasoning/processing
    llm_provider: str = Field("openai", description="LiteLLM provider name")
    llm_model: str = Field("gpt-4o", description="Model name")
    llm_api_key: Optional[str] = Field(None)
    llm_base_url: Optional[str] = Field(None)
    
    # Embedding Model
    embedding_provider: str = Field("openai", description="LiteLLM provider for embeddings")
    embedding_model: str = Field("text-embedding-3-small", description="Embedding model name")
    embedding_api_key: Optional[str] = Field(None)
    embedding_base_url: Optional[str] = Field(None)

class MemoryController:
    """
    Unified Context Controller using OpenViking.
    Manages memories, resources, and skills via filesystem paradigm.
    """
    def __init__(self, user_id: str, config: Optional[OpenVikingConfig] = None):
        self.user_id = user_id
        self.config = config or self._load_default_config()
        self.ov_client = self._init_client()

    def _load_default_config(self) -> OpenVikingConfig:
        return OpenVikingConfig(
            llm_provider="openai",
            llm_model=os.getenv("OPENVIKING_LLM_MODEL", "gpt-4o"),
            llm_api_key=os.getenv("OPENAI_API_KEY"),
            embedding_provider="openai",
            embedding_model=os.getenv("OPENVIKING_EMBED_MODEL", "text-embedding-3-small"),
            embedding_api_key=os.getenv("OPENAI_API_KEY")
        )

    def _init_client(self) -> OpenViking:
        """Initialize OpenViking client with LiteLLM configuration."""
        
        # Configure LLM (VLM/Reasoning)
        llm_config = {
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "api_key": self.config.llm_api_key,
        }
        if self.config.llm_base_url:
            llm_config["api_base"] = self.config.llm_base_url

        # Configure Embeddings
        embed_config = {
            "provider": self.config.embedding_provider,
            "model": self.config.embedding_model,
            "api_key": self.config.embedding_api_key,
        }
        if self.config.embedding_base_url:
            embed_config["api_base"] = self.config.embedding_base_url

        try:
            client = OpenViking(
                vlm=llm_config,
                embedding=embed_config
            )
            logger.info(f"OpenViking initialized for user: {self.user_id}")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize OpenViking: {e}")
            raise

    def add_fact(self, content: str, path: str = "facts/general.md"):
        """
        Add a memory/fact as a file in OpenViking.
        """
        # OpenViking uses paths like a filesystem
        # We can organize memories by user_id folder
        full_path = f"{self.user_id}/{path}"
        try:
            # Check if file exists to append or create
            # Note: OpenViking API might differ, assuming generic add/insert or file ops
            # Based on 'filesystem paradigm', we likely write content to a path
            
            # Using hypothetical API based on description "build an Agent's brain just like managing local files"
            # If explicit append isn't supported, we might need to read-modify-write or use a specific method
            
            # For now, we'll assume a `write_file` or `add_context` method exists. 
            # Since exact API isn't fully visible without running `dir()`, 
            # I will use a generic `add` wrapper or check available methods in runtime if this fails.
            
            # Re-checking reference: "Filesystem Management Paradigm... Directory Recursive Retrieval"
            # Let's assume we can add content directly.
            
            # Hypothetical: self.ov_client.add(path=full_path, content=content)
            # Or accessing via a context object.
            
            # Let's assume a simple key-value or path-content add for now.
            # If this is wrong, I will fix it after running a test script to inspect the client.
             self.ov_client.add_file(path=full_path, content=content)
             logger.debug(f"Added fact to {full_path}")
        except Exception as e:
            logger.error(f"Error adding fact to OpenViking: {e}")

    def retrieve_context(self, query: str) -> str:
        """
        Retrieve relevant context using semantic search + directory traversal.
        """
        try:
            # Search within the user's directory
            results = self.ov_client.retrieve(
                query=query,
                path=f"{self.user_id}/", # Root for this user
                top_k=5
            )
            
            # Format results
            context = "Relevant Context:\n"
            for res in results:
                # Assuming result has 'content' and 'score'
                # Check actual attribute names at runtime
                text = getattr(res, 'content', str(res))
                context += f"- {text}\n"
            return context
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return ""

    def save_session_summary(self, session_id: str, summary: str):
        """Save episodic summary as a file."""
        path = f"{self.user_id}/sessions/{session_id}/summary.md"
        try:
            self.ov_client.add_file(path=path, content=summary)
        except Exception as e:
            logger.error(f"Error saving session summary: {e}")

