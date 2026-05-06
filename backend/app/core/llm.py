import os
import logging
from typing import Any, Dict, List, Optional, Union, AsyncGenerator

from litellm import completion, acompletion
from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.core.llm")


def _get_cost_monitor():
    try:
        from app.core.cost_monitor import get_cost_monitor
        return get_cost_monitor()
    except Exception:
        return None

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
        # In-memory per-provider key/url overrides loaded from provider_config
        self._provider_keys: Dict[str, Dict[str, Optional[str]]] = {}
        self._setup_litellm()
        self._load_from_provider_config()

    def _setup_litellm(self):
        """Configure global LiteLM settings."""
        # Enable caching if Redis is available (future optimization)
        # litellm.cache = ...
        pass

    def _load_from_provider_config(self) -> None:
        """Populate _provider_keys from persisted provider_config (if available)."""
        try:
            from app.core.provider_config import get_provider_config
            svc = get_provider_config()
            for provider_name in ("gemini", "openai", "anthropic", "groq", "mistral", "ollama"):
                key = svc.get_api_key(provider_name)
                base_url = svc.get_base_url(provider_name)
                if key or base_url:
                    self._provider_keys[provider_name] = {"api_key": key, "base_url": base_url}
        except Exception as exc:
            logger.debug(f"Could not load provider config at startup: {exc}")

    def update_provider(self, name: str, api_key: Optional[str], base_url: Optional[str] = None) -> None:
        """
        Hot-reload API key and/or base URL for a provider without restarting.
        If the updated provider is the current default, also patches default_config.
        """
        self._provider_keys[name] = {"api_key": api_key, "base_url": base_url}
        if self.default_config.provider == name:
            self.default_config = ModelConfig(
                provider=self.default_config.provider,
                model_name=self.default_config.model_name,
                temperature=self.default_config.temperature,
                max_tokens=self.default_config.max_tokens,
                api_key=api_key or self.default_config.api_key,
                base_url=base_url or self.default_config.base_url,
            )
        logger.info(f"Provider '{name}' reloaded (has_key={bool(api_key)})")

    def get_api_key(self, name: str) -> Optional[str]:
        """
        Return the API key for the named provider.
        Checks in-memory cache first (populated by update_provider / startup load),
        then falls back to the unified key lookup (env vars, etc.).
        """
        cached = self._provider_keys.get(name)
        if cached and cached.get("api_key"):
            return cached["api_key"]

        try:
            from app.core.provider_config import get_api_key_fallback
            return get_api_key_fallback(name)
        except Exception as exc:
            logger.debug(f"Could not retrieve API key for {name}: {exc}")
            return None

    def get_base_url(self, name: str) -> Optional[str]:
        """Return the configured base URL for a provider (e.g., Ollama)."""
        cached = self._provider_keys.get(name)
        if cached:
            return cached.get("base_url")
        return None

    async def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        response_format: Optional[Any] = None,
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
            kwargs: Dict[str, Any] = dict(
                model=model_id,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                tools=tools,
                stream=stream,
            )
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = await acompletion(**kwargs)

            if not stream:
                try:
                    usage = getattr(response, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                        output_tokens = getattr(usage, "completion_tokens", 0) or 0
                        cost_monitor = _get_cost_monitor()
                        if cost_monitor and (input_tokens > 0 or output_tokens > 0):
                            try:
                                cost_monitor.record_call(
                                    session_id="default",
                                    user_id="default",
                                    provider=cfg.provider,
                                    model=cfg.model_name,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

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
