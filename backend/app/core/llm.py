import os
import logging
from typing import Any, Dict, List, Optional, Union, AsyncGenerator

from litellm import completion, acompletion
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger("navibot.core.llm")

class ModelConfig(BaseModel):
    """Configuration for LLM model selection and parameters."""
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic', 'gemini')")
    model_name: str = Field(..., description="Specific model identifier (e.g., 'gpt-4o', 'gemini-1.5-pro')")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    api_key: Optional[str] = Field(None, description="Optional API key override")
    base_url: Optional[str] = Field(None, description="Optional base URL for local models")

class LLMService:
    """
    Abstraction layer for LLM interactions using LiteLM.
    Supports multiple providers and local models.
    """

    def __init__(self, default_config: Optional[ModelConfig] = None):
        self.default_config = default_config or ModelConfig(
            provider="gemini",
            model_name="gemini-flash-lite-latest",
            temperature=0.7
        )
        self._setup_litellm()

    def _setup_litellm(self):
        """Configure global LiteLM settings."""
        # Enable caching if Redis is available (future optimization)
        # litellm.cache = ...
        pass

    async def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[Any, None]]:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dictionaries (role, content).
            config: Optional model configuration override.
            tools: Optional list of tool definitions (OpenAI format).
            stream: Whether to stream the response.
            
        Returns:
            The completion response or an async generator if streaming.
        """
        cfg = config or self.default_config
        model_id = f"{cfg.provider}/{cfg.model_name}" if cfg.provider != "openai" else cfg.model_name

        try:
            logger.info(f"Generating with model: {model_id}")
            response = await acompletion(
                model=model_id,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                tools=tools,
                stream=stream
            )
            return response

        except Exception as e:
            logger.error(f"LLM Generation Error: {str(e)}")
            raise

    def get_model_id(self, config: ModelConfig) -> str:
        """Helper to format model ID for LiteLM."""
        if config.provider == "openai":
            return config.model_name
        return f"{config.provider}/{config.model_name}"

# Singleton instance for easy access
default_llm = LLMService()
