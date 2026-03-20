import pytest
import json
from app.core.prompt_composer import PromptComposer, get_prompt_composer


class TestPromptComposer:
    def setup_method(self):
        self.composer = PromptComposer()

    def test_compose_no_injection(self):
        base = "You are a helpful assistant."
        result = self.composer.compose(base, "Hello, how are you?")
        assert result == base

    def test_compose_financial_injection(self):
        base = "You are a helpful assistant."
        result = self.composer.compose(base, "Necesito registrar mis gastos de comida")
        assert "Financial Guidelines" in result or "gastos" in result.lower()

    def test_compose_research_injection(self):
        base = "You are a helpful assistant."
        result = self.composer.compose(base, "Busca información sobre cambio climático")
        assert "Research" in result or "busca" in result.lower()

    def test_compose_coding_injection(self):
        base = "You are a helpful assistant."
        result = self.composer.compose(base, "Ejecuta este código python")
        assert "Code Execution" in result or "python" in result.lower()

    def test_get_applicable_injections_financial(self):
        injections = self.composer.get_applicable_injections("Mis gastos del mes fueron 500 USD")
        assert len(injections) > 0
        assert any("financial" in i.description.lower() or "gasto" in i.description.lower() for i in injections)

    def test_get_applicable_injections_social(self):
        injections = self.composer.get_applicable_injections("Publica esto en Instagram")
        assert len(injections) > 0

    def test_get_applicable_injections_research(self):
        injections = self.composer.get_applicable_injections("Investigar las causas del cambio climatico")
        assert len(injections) > 0

    def test_get_applicable_injections_coding(self):
        injections = self.composer.get_applicable_injections("Run this Python script please")
        assert len(injections) > 0

    def test_no_injection_for_generic(self):
        injections = self.composer.get_applicable_injections("Hola, que tal?")
        assert len(injections) == 0

    def test_get_registered_injections(self):
        registered = self.composer.get_registered_injections()
        assert len(registered) >= 4
        assert any("financial" in r["description"].lower() for r in registered)

    def test_singleton(self):
        c1 = get_prompt_composer()
        c2 = get_prompt_composer()
        assert c1 is c2
