import pytest
from app.core.llm import LLMService
from app.skills.registry import ToolRegistry

def test_imports():
    """Verify that core modules can be imported without errors."""
    try:
        from app.core.agent_graph import AgentGraph
        assert True
    except ImportError as e:
        pytest.fail(f"ImportError: {e}")

def test_llm_service_initialization():
    """Verify LLMService initializes correctly."""
    llm = LLMService()
    assert llm.default_config.provider == "gemini"

def test_tool_registry():
    """Verify ToolRegistry works as expected."""
    registry = ToolRegistry()
    
    @registry.register(name="test_tool", description="A test tool")
    def test_func(x: int) -> int:
        return x * 2

    assert "test_tool" in registry._tools
    tool = registry.get_tool("test_tool")
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
