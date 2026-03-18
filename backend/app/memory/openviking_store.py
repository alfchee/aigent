import logging
import os
import tempfile
import uuid
from pathlib import Path
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
            llm_provider=os.getenv("OPENVIKING_LLM_PROVIDER", "openai"),
            llm_model=os.getenv("OPENVIKING_LLM_MODEL", "gpt-4o"),
            llm_api_key=os.getenv("OPENVIKING_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            llm_base_url=os.getenv("OPENVIKING_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            embedding_provider=os.getenv("OPENVIKING_EMBED_PROVIDER", "openai"),
            embedding_model=os.getenv("OPENVIKING_EMBED_MODEL", "text-embedding-3-small"),
            embedding_api_key=os.getenv("OPENVIKING_EMBED_API_KEY") or os.getenv("OPENAI_API_KEY"),
            embedding_base_url=os.getenv("OPENVIKING_EMBED_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
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

    def _user_root_uri(self) -> str:
        return f"/user/{self.user_id}"

    def _resource_uri(self, path: str) -> str:
        normalized = Path(path.strip("/")).as_posix()
        return f"{self._user_root_uri()}/{normalized}"

    def _ensure_parent_dirs(self, uri: str) -> None:
        parts = uri.strip("/").split("/")[:-1]
        current = ""
        for part in parts:
            current += f"/{part}"
            try:
                self.ov_client.mkdir(current)
            except Exception:
                pass

    def add_fact(self, content: str, path: str = "facts/general.md") -> None:
        target_uri = self._resource_uri(path)
        self._ensure_parent_dirs(target_uri)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=f"_{uuid.uuid4().hex[:8]}.md",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(content)
            source_path = handle.name
        try:
            response = self.ov_client.add_resource(
                path=source_path,
                to=target_uri,
                wait=True,
                build_index=True,
                summarize=False,
            )
            if response.get("status") not in {"ok", "success"}:
                logger.error("OpenViking add_resource failed: %s", response)
        finally:
            try:
                os.remove(source_path)
            except Exception:
                pass

    def retrieve_context(self, query: str) -> str:
        try:
            result = self.ov_client.search(query=query, target_uri=self._user_root_uri(), limit=5)
        except Exception as exc:
            logger.error("Error retrieving context: %s", exc)
            return ""
        snippets = []
        uris_to_read = []
        for section in ("memories", "resources", "skills"):
            items = getattr(result, section, []) or []
            for item in items:
                uri_value = getattr(item, "uri", None)
                if uri_value:
                    uris_to_read.append(str(uri_value))
                for attr in ("content", "text", "summary", "description", "uri", "title"):
                    value = getattr(item, attr, None)
                    if value:
                        snippets.append(str(value))
                        break
        if not snippets:
            for query_result in getattr(result, "query_results", []) or []:
                for matched in getattr(query_result, "matched_contexts", []) or []:
                    snippets.append(str(getattr(matched, "content", matched)))
        if not snippets:
            return ""
        expanded = []
        for snippet in snippets:
            if snippet.startswith("viking://"):
                uri = snippet.replace("viking://", "/", 1)
                try:
                    content = self.ov_client.read(uri, offset=0, limit=-1)
                except Exception:
                    content = ""
                if content:
                    expanded.append(content.strip())
                else:
                    expanded.append(snippet)
            else:
                expanded.append(snippet)
        context = "Relevant Context:\n"
        for snippet in expanded[:5]:
            context += f"- {snippet}\n"
        return context

    def save_session_summary(self, session_id: str, summary: str) -> None:
        self.add_fact(summary, path=f"sessions/{session_id}/summary.md")
