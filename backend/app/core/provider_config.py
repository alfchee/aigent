"""
ProviderConfigService — encrypted runtime provider/API-key management.

Keys are stored in workspace/config/providers.json, encrypted with Fernet
using a key derived from AIGENT_SECRET.  The plaintext value of any key is
NEVER returned through the public API; callers only receive `has_key: bool`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from app.core.paths import workspace_config_dir

logger = logging.getLogger("navibot.core.provider_config")

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

KNOWN_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "label": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "test_model": "gemini/gemini-flash-lite-latest",
        "needs_key": True,
        "default_model": "gemini-flash-lite-latest",
        "available_models": [
            "gemini-2.5-pro-preview-03-25",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-flash-lite-latest",
        ],
    },
    "openai": {
        "label": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "test_model": "gpt-4o-mini",
        "needs_key": True,
        "default_model": "gpt-4o-mini",
        "available_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
    },
    "anthropic": {
        "label": "Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "test_model": "anthropic/claude-3-haiku-20240307",
        "needs_key": True,
        "default_model": "claude-3-haiku-20240307",
        "available_models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ],
    },
    "groq": {
        "label": "Groq",
        "env_key": "GROQ_API_KEY",
        "test_model": "groq/llama3-8b-8192",
        "needs_key": True,
        "default_model": "llama3-8b-8192",
        "available_models": [
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it",
        ],
    },
    "mistral": {
        "label": "Mistral",
        "env_key": "MISTRAL_API_KEY",
        "test_model": "mistral/mistral-small",
        "needs_key": True,
        "default_model": "mistral-small",
        "available_models": [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "mistral-small",
        ],
    },
    "ollama": {
        "label": "Ollama",
        "env_key": None,
        "test_model": "ollama/llama3",
        "needs_key": False,
        "default_model": "llama3",
        "available_models": [],  # dynamic via /api/tags
    },
}

# ---------------------------------------------------------------------------
# Model parsing helpers
# ---------------------------------------------------------------------------

def parse_test_model(test_model: str) -> tuple[str, str]:
    """
    Parse a test_model string into (provider, model_name).

    Format: "provider/model" (e.g., "groq/llama3-8b-8192")
    Special case: OpenAI uses plain model name without prefix (e.g., "gpt-4o-mini")
    """
    provider_part, _, model_part = test_model.partition("/")
    if not model_part:
        return "openai", provider_part
    return provider_part, model_part


# ---------------------------------------------------------------------------
# Fernet helper
# ---------------------------------------------------------------------------

def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from an arbitrary string secret."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet():
    """Return a Fernet instance if cryptography is available and secret is set."""
    secret = os.environ.get("AIGENT_SECRET", "").strip()
    if not secret:
        return None
    try:
        from cryptography.fernet import Fernet
        key = _derive_fernet_key(secret)
        return Fernet(key)
    except ImportError:
        logger.warning("cryptography package not installed; keys stored unencrypted")
        return None


# ---------------------------------------------------------------------------
# Unified API key lookup
# ---------------------------------------------------------------------------

def get_api_key_fallback(provider_name: str, encrypted_value: Optional[str] = None) -> Optional[str]:
    """
    Return the plaintext API key for a provider.
    First tries decryption of stored/encrypted value, then falls back to environment.
    This single function is used by both ProviderConfigService and LLMService.
    """
    if encrypted_value:
        fernet = _get_fernet()
        if fernet is not None:
            try:
                return fernet.decrypt(encrypted_value.encode()).decode()
            except Exception as exc:
                logger.debug(f"Failed to decrypt key for {provider_name}: {exc}")
        else:
            return encrypted_value

    env_var = KNOWN_PROVIDERS.get(provider_name, {}).get("env_key")
    if env_var:
        return os.environ.get(env_var) or None

    return None


# ---------------------------------------------------------------------------
# Provider config service
# ---------------------------------------------------------------------------

ProviderStatus = Literal["configured", "missing", "untested"]


class ProviderConfigService:
    """
    Manages runtime provider configuration, including encrypted API key storage.
    """

    _PROVIDERS_FILE = "providers.json"

    def __init__(self) -> None:
        self._path = workspace_config_dir() / self._PROVIDERS_FILE
        # In-memory store: { provider_name: {api_key, base_url, default_model} }
        self._store: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal persistence
    # ------------------------------------------------------------------

    def _encrypt(self, value: str) -> str:
        fernet = _get_fernet()
        if fernet is None:
            return value
        return fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        fernet = _get_fernet()
        if fernet is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception as exc:
            logger.error(
                f"Decryption failed for stored value: {exc}. "
                "This may indicate: (1) corrupted data, (2) AIGENT_SECRET changed, or (3) data was stored unencrypted. "
                "Falling back to plaintext retrieval; verify if this is expected."
            )
            return value

    def _load(self) -> None:
        if not self._path.exists():
            logger.debug("providers.json not found; starting with empty store")
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            entries: List[Dict[str, Any]] = json.loads(raw)
            for entry in entries:
                name = entry.get("name")
                if not name:
                    continue
                self._store[name] = {
                    "api_key": entry.get("api_key"),  # encrypted blob or None
                    "base_url": entry.get("base_url"),
                    "default_model": entry.get("default_model"),
                }
        except Exception as exc:
            logger.error(f"Failed to load providers.json: {exc}")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entries = [
            {
                "name": name,
                "api_key": data.get("api_key"),
                "base_url": data.get("base_url"),
                "default_model": data.get("default_model"),
            }
            for name, data in self._store.items()
        ]
        self._path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_providers(self) -> List[Dict[str, Any]]:
        """
        Return status for all known providers.
        Never includes plaintext API keys.
        """
        result = []
        for name, meta in KNOWN_PROVIDERS.items():
            stored = self._store.get(name, {})
            has_stored_key = bool(stored.get("api_key"))

            # Fall back to env var
            env_var = meta.get("env_key")
            has_env_key = bool(env_var and os.environ.get(env_var, "").strip())

            has_key = has_stored_key or has_env_key

            if meta["needs_key"]:
                if has_stored_key:
                    status: ProviderStatus = "configured"
                elif has_env_key:
                    status = "configured"
                else:
                    status = "missing"
            else:
                # Ollama or similar — no key required
                status = "configured"

            result.append({
                "name": name,
                "label": meta["label"],
                "status": status,
                "has_key": has_key,
                "base_url": stored.get("base_url"),
                "default_model": stored.get("default_model") or meta["default_model"],
                "available_models": meta["available_models"],
                "needs_key": meta["needs_key"],
            })
        return result

    def update_providers(self, updates: List[Dict[str, Any]]) -> None:
        """
        Persist provider updates (api_key, base_url, default_model).
        api_key values are encrypted before being stored.
        Triggers LLMService hot-reload for each updated provider.
        """
        for update in updates:
            name = update.get("name")
            if name not in KNOWN_PROVIDERS:
                logger.warning(f"Unknown provider in update: {name!r}; skipping")
                continue
            entry = self._store.setdefault(name, {})

            api_key = update.get("api_key")
            if api_key is not None:
                # Empty string means "clear key"
                entry["api_key"] = self._encrypt(api_key) if api_key else None

            if "base_url" in update:
                entry["base_url"] = update["base_url"] or None

            if "default_model" in update:
                entry["default_model"] = update["default_model"] or None

        self._save()

        # Hot-reload LLMService (delayed import to avoid circular dep)
        try:
            from app.core.llm import default_llm
            for update in updates:
                name = update.get("name")
                if not name:
                    continue
                plaintext_key = self.get_api_key(name)
                base_url = self._store.get(name, {}).get("base_url")
                default_llm.update_provider(name, plaintext_key, base_url)
        except Exception as exc:
            logger.error(f"Failed to hot-reload LLMService after provider update: {exc}")

    def get_api_key(self, name: str) -> Optional[str]:
        """
        Return the decrypted API key for a provider.
        Checks persisted store first, falls back to environment variable.
        NEVER exposed through the public HTTP API.
        """
        stored = self._store.get(name, {})
        encrypted = stored.get("api_key")
        return get_api_key_fallback(name, encrypted)

    def get_base_url(self, name: str) -> Optional[str]:
        """Return the configured base_url for a provider (e.g., Ollama)."""
        return self._store.get(name, {}).get("base_url")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ProviderConfigService] = None


def get_provider_config() -> ProviderConfigService:
    global _instance
    if _instance is None:
        _instance = ProviderConfigService()
    return _instance
