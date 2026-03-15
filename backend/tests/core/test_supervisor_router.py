import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from app.core import supervisor as supervisor_module


class _FakePrompt:
    def partial(self, **kwargs):
        return self

    def __or__(self, other):
        return _FakeChain([self, other])

    async def ainvoke(self, value):
        return value


class _FakeChain:
    def __init__(self, parts):
        self.parts = parts

    def __or__(self, other):
        return _FakeChain(self.parts + [other])

    async def ainvoke(self, value):
        current = value
        for part in self.parts:
            if hasattr(part, "ainvoke"):
                current = await part.ainvoke(current)
        return current


class _FakeParser:
    async def ainvoke(self, value):
        return value


class _FakeLLM:
    def __init__(self, next_value):
        self.next_value = next_value
        self.last_messages = None

    def bind_tools(self, tools, tool_choice):
        return _FakeBoundLLM(self)


class _FakeBoundLLM:
    def __init__(self, parent):
        self.parent = parent

    async def ainvoke(self, value):
        self.parent.last_messages = value.get("messages", [])
        return {"next": self.parent.next_value}


class TestSupervisorRouter(unittest.IsolatedAsyncioTestCase):
    async def test_routes_linkedin_requests_to_webnavigator(self):
        llm = _FakeLLM("GeneralAssistant")
        with patch.object(supervisor_module.ChatPromptTemplate, "from_messages", return_value=_FakePrompt()), \
             patch.object(supervisor_module, "JsonOutputFunctionsParser", return_value=_FakeParser()):
            node = supervisor_module.create_supervisor_node(llm, supervisor_module.WORKERS)

        state = {
            "messages": [HumanMessage(content="Obtén información de mi perfil de LinkedIn")],
            "worker_calls": 0,
        }
        result = await node(state)
        self.assertEqual(result["next"], "WebNavigator")
        self.assertEqual(result["worker_calls"], 1)

    async def test_reroutes_finish_without_worker_output_to_webnavigator(self):
        llm = _FakeLLM("FINISH")
        with patch.object(supervisor_module.ChatPromptTemplate, "from_messages", return_value=_FakePrompt()), \
             patch.object(supervisor_module, "JsonOutputFunctionsParser", return_value=_FakeParser()):
            node = supervisor_module.create_supervisor_node(llm, supervisor_module.WORKERS)

        state = {
            "messages": [HumanMessage(content="Busca en internet noticias de IA")],
            "worker_calls": 0,
        }
        result = await node(state)
        self.assertEqual(result["next"], "WebNavigator")
        self.assertEqual(result["worker_calls"], 1)

    async def test_forces_finish_when_worker_output_exists_and_limit_reached(self):
        llm = _FakeLLM("WebNavigator")
        with patch.object(supervisor_module.ChatPromptTemplate, "from_messages", return_value=_FakePrompt()), \
             patch.object(supervisor_module, "JsonOutputFunctionsParser", return_value=_FakeParser()):
            node = supervisor_module.create_supervisor_node(llm, supervisor_module.WORKERS)

        state = {
            "messages": [
                HumanMessage(content="hola"),
                AIMessage(content="respuesta final", name="GeneralAssistant"),
            ],
            "worker_calls": 4,
        }
        result = await node(state)
        self.assertEqual(result["next"], "FINISH")
        self.assertEqual(result["worker_calls"], 4)

    async def test_sanitizes_empty_messages_before_llm_invoke(self):
        llm = _FakeLLM("GeneralAssistant")
        with patch.object(supervisor_module.ChatPromptTemplate, "from_messages", return_value=_FakePrompt()), \
             patch.object(supervisor_module, "JsonOutputFunctionsParser", return_value=_FakeParser()):
            node = supervisor_module.create_supervisor_node(llm, supervisor_module.WORKERS)

        state = {
            "messages": [SimpleNamespace(content="   ", type="human")],
            "worker_calls": 0,
        }
        result = await node(state)
        self.assertEqual(result["next"], "GeneralAssistant")
        self.assertEqual(result["worker_calls"], 1)
        self.assertTrue(llm.last_messages)
        self.assertTrue(str(llm.last_messages[-1].content).strip())
