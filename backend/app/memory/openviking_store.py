import logging
import os
from typing import Optional

from openviking import OpenViking
from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.memory.openviking")


class OpenVikingConfig(BaseModel):
    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-4o")
    llm_api_key: Optional[str] = Field(default=None)
    llm_base_url: Optional[str] = Field(default=None)
    embedding_provider: str = Field(default="openai")
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_api_key: Optional[str] = Field(default=None)
    embedding_base_url: Optional[str] = Field(default=None)


class MemoryController:
    def __init__(self, user_id: str, config: Optional[OpenVikingConfig] = None):
        self.user_id = user_id
        self.config = config or self._load_default_config()
        self.ov_client = self._init_client()

    def _load_default_config(self) -> OpenVikingConfig:
        return OpenVikingConfig(
            llm_model=os.getenv("OPENVIKING_LLM_MODEL", "gpt-4o"),
            llm_api_key=os.getenv("OPENAI_API_KEY"),
            embedding_model=os.getenv("OPENVIKING_EMBED_MODEL", "text-embedding-3-small"),
            embedding_api_key=os.getenv("OPENAI_API_KEY"),
        )

    def _init_client(self) -> OpenViking:
        llm_config = {
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "api_key": self.config.llm_api_key,
        }
        if self.config.llm_base_url:
            llm_config["api_base"] = self.config.llm_base_url

        embed_config = {
            "provider": self.config.embedding_provider,
            "model": self.config.embedding_model,
            "api_key": self.config.embedding_api_key,
        }
        if self.config.embedding_base_url:
            embed_config["api_base"] = self.config.embedding_base_url

        client = OpenViking(vlm=llm_config, embedding=embed_config)
        logger.info("OpenViking initialized for user: %s", self.user_id)
        return client

    def add_fact(self, content: str, path: str = "facts/general.md") -> None:
        full_path = f"{self.user_id}/{path}"
        self.ov_client.add_file(path=full_path, content=content)

    def retrieve_context(self, query: str) -> str:
        try:
            results = self.ov_client.retrieve(query=query, path=f"{self.user_id}/", top_k=5)
        except Exception as exc:
            logger.error("Error retrieving context: %s", exc)
            return ""
        context = "Relevant Context:\n"
        for result in results:
            context += f"- {getattr(result, 'content', str(result))}\n"
        return context

    def save_session_summary(self, session_id: str, summary: str) -> None:
        path = f"{self.user_id}/sessions/{session_id}/summary.md"
        self.ov_client.add_file(path=path, content=summary)
