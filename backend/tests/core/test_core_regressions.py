import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _DummyGenerator:
    def __init__(self, value):
        self._value = value

    def __iter__(self):
        return self

    def __next__(self):
        if self._value is None:
            raise StopIteration
        value = self._value
        self._value = None
        return value

    def close(self):
        return None


class TestCoreRegressions(unittest.TestCase):
    def test_get_agent_model_openrouter_without_langchain_openai_falls_back_to_google(self):
        from app.core import llm_factory

        provider = SimpleNamespace(
            provider_id="openrouter",
            api_key_enc=None,
            config_json=None,
            base_url=None,
        )
        dummy_db = MagicMock()
        dummy_gen = _DummyGenerator(dummy_db)

        with patch.object(llm_factory, "get_persistence_db", return_value=dummy_gen), \
             patch.object(llm_factory, "get_active_provider_config", return_value=provider), \
             patch.object(llm_factory, "ChatOpenAI", None), \
             patch.object(llm_factory, "ChatGoogleGenerativeAI", return_value="google_fallback"), \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=False):
            model = llm_factory.get_agent_model("gemini-2.0-flash")

        self.assertEqual(model, "google_fallback")

    def test_conversation_summarizer_replaces_deprecated_model(self):
        from app.core.conversation_summarizer import ConversationSummarizer

        ConversationSummarizer._instance = None
        with patch.dict(os.environ, {"NAVIBOT_SUMMARIZER_MODEL": "gemini-2.0-flash-lite"}, clear=False):
            summarizer = ConversationSummarizer()
        self.assertEqual(summarizer._summarizer_model, "gemini-2.0-flash")
        ConversationSummarizer._instance = None
