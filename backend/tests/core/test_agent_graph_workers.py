import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from app.core.agent_graph import AgentGraph


class _FakeCompiledGraph:
    def __init__(self, nodes):
        self.nodes = nodes


class _FakeStateGraph:
    def __init__(self, state_type):
        self.nodes = {}

    def add_node(self, name, node):
        self.nodes[name] = node

    def add_edge(self, a, b):
        return None

    def add_conditional_edges(self, a, b, c):
        return None

    def compile(self, checkpointer=None):
        return _FakeCompiledGraph(self.nodes)


class _FakeCacheManager:
    def get_or_create_worker_cache(self, worker_name, system_instruction, tools_schema):
        return None


class _FakeLLM:
    def __init__(self):
        self.invocations = []

    def bind_tools(self, tools):
        return _FakeBoundLLM(tools, self)


class _FakeBoundLLM:
    def __init__(self, tools, parent):
        self.tools = tools
        self.calls = 0
        self.parent = parent

    async def ainvoke(self, messages):
        self.calls += 1
        self.parent.invocations.append(messages)
        first_tool_name = getattr(self.tools[0], "__name__", "unknown_tool")
        if self.calls == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[{"name": first_tool_name, "args": {}, "id": "tool-call-1"}],
            )
        return SimpleNamespace(content=f"done-{first_tool_name}", tool_calls=[])


class _FakeSkillLoader:
    def load_skills_map(self):
        return {
            "browser": [search_brave],
            "search": [],
            "reader": [],
            "calendar": [],
            "scheduler": [],
            "workspace": [],
            "code_execution": [],
            "google_drive": [],
            "google_workspace_manager": [],
            "memory": [],
            "telegram": [],
            "extra_tools": [],
            "image_generation": [generate_image],
        }


class _FakeSecureSkillLoader:
    def load_skills(self):
        return {}


async def _fake_supervisor_node(state):
    return {"next": "FINISH"}


def search_brave():
    return "search-result"


def generate_image():
    return "image-result"


class TestAgentGraphWorkers(unittest.IsolatedAsyncioTestCase):
    async def test_worker_tools_are_isolated_per_worker_node(self):
        fake_llm = _FakeLLM()
        with patch("app.core.agent_graph.StateGraph", _FakeStateGraph), \
             patch("app.core.agent_graph.SkillLoader", _FakeSkillLoader), \
             patch("app.core.agent_graph.SecureSkillLoader", _FakeSecureSkillLoader), \
             patch("app.core.agent_graph.create_supervisor_node", return_value=_fake_supervisor_node), \
             patch("app.core.agent_graph.prompt_cache.get_cache_manager", return_value=_FakeCacheManager()), \
             patch("app.core.config_manager.get_settings", return_value=SimpleNamespace(system_prompt="You are NaviBot test identity.")), \
             patch.object(AgentGraph, "_get_llm", return_value=fake_llm):
            graph = AgentGraph(use_registry=False)

        web_node = graph.graph.nodes["WebNavigator"]
        image_node = graph.graph.nodes["ImageGenerator"]

        state = {"messages": [HumanMessage(content="test")], "worker_calls": 0}
        web_result = await web_node(state)
        image_result = await image_node(state)

        self.assertEqual(web_result["messages"][0].name, "WebNavigator")
        self.assertIn("done-search_brave", web_result["messages"][0].content)
        self.assertEqual(image_result["messages"][0].name, "ImageGenerator")
        self.assertIn("done-generate_image", image_result["messages"][0].content)
        self.assertTrue(fake_llm.invocations)
        self.assertIn("You are NaviBot test identity.", fake_llm.invocations[0][0].content)

    async def test_workers_do_not_use_cached_content_with_bind_tools(self):
        fake_llm = _FakeLLM()
        llm_calls = []

        def _fake_get_llm(role_name, cached_content=None):
            llm_calls.append((role_name, cached_content))
            return fake_llm

        with patch("app.core.agent_graph.StateGraph", _FakeStateGraph), \
             patch("app.core.agent_graph.SkillLoader", _FakeSkillLoader), \
             patch("app.core.agent_graph.SecureSkillLoader", _FakeSecureSkillLoader), \
             patch("app.core.agent_graph.create_supervisor_node", return_value=_fake_supervisor_node), \
             patch("app.core.agent_graph.prompt_cache.get_cache_manager", return_value=_FakeCacheManager()), \
             patch("app.core.config_manager.get_settings", return_value=SimpleNamespace(system_prompt="You are NaviBot test identity.")), \
             patch.object(AgentGraph, "_get_llm", side_effect=_fake_get_llm):
            AgentGraph(use_registry=False)

        worker_roles = {"WebNavigator", "CalendarManager", "GeneralAssistant", "ImageGenerator"}
        for role_name, cached_content in llm_calls:
            if role_name in worker_roles:
                self.assertIsNone(cached_content)
