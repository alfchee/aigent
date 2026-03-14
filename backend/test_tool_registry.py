#!/usr/bin/env python3
"""
Test script para verificar la implementación de ToolRegistry y ToolExecutor.
"""

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.tools import tool


# Test tools
@tool
def test_add(a: int, b: int) -> int:
    """Adds two numbers together.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        The sum of a and b
    """
    return a + b


@tool
async def test_multiply(a: int, b: int = 1) -> int:
    """Multiplies two numbers.
    
    Args:
        a: First number
        b: Second number (default: 1)
    
    Returns:
        The product of a and b
    """
    return a * b


async def main():
    print("=" * 60)
    print("Testing ToolRegistry and ToolExecutor")
    print("=" * 60)
    
    # Import after path is set
    from app.core.tool_registry import ToolRegistry, ToolMetadata, get_tool_registry
    from app.core.tool_executor import ToolExecutor, get_tool_executor
    
    # Test 1: ToolRegistry creation
    print("\n[TEST 1] ToolRegistry creation...")
    try:
        registry = ToolRegistry()
        print(f"  ✓ ToolRegistry instance created")
        print(f"  ✓ Initialized: {registry.is_initialized}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 2: Register tools
    print("\n[TEST 2] Register tools...")
    try:
        # Register sync tool
        await registry.register_tool(
            test_add,
            ToolMetadata(
                name="test_add",
                source="skill",
                category="utility",
                description="Adds two numbers"
            )
        )
        
        # Register async tool
        await registry.register_tool(
            test_multiply,
            ToolMetadata(
                name="test_multiply",
                source="skill",
                category="utility",
                description="Multiplies two numbers"
            )
        )
        
        stats = registry.get_stats()
        print(f"  ✓ Registered {stats['total_tools']} tools")
        print(f"  ✓ Stats: {stats}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 3: Get tools
    print("\n[TEST 3] Get tools...")
    try:
        tool = await registry.get_tool("test_add")
        print(f"  ✓ Got tool: {tool.name}")
        
        all_tools = await registry.get_all_tools()
        print(f"  ✓ All tools count: {len(all_tools)}")
        
        by_source = await registry.get_tools_by_source("skill")
        print(f"  ✓ Tools by source (skill): {len(by_source)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 4: ToolExecutor creation
    print("\n[TEST 4] ToolExecutor creation...")
    try:
        executor = ToolExecutor(registry)
        print(f"  ✓ ToolExecutor created with registry")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 5: Execute tool successfully
    print("\n[TEST 5] Execute tool (success)...")
    try:
        result = await executor.execute(
            "test_add",
            {"a": 5, "b": 3}
        )
        print(f"  ✓ Result: {result}")
        assert result["success"] == True
        assert result["result"] == 8
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 6: Execute async tool
    print("\n[TEST 6] Execute async tool...")
    try:
        result = await executor.execute(
            "test_multiply",
            {"a": 4, "b": 7}
        )
        print(f"  ✓ Result: {result}")
        assert result["success"] == True
        assert result["result"] == 28
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 7: Execute tool with validation error
    print("\n[TEST 7] Execute tool (validation error)...")
    try:
        result = await executor.execute(
            "test_add",
            {"a": 5}  # Missing 'b' parameter
        )
        print(f"  ✓ Result: {result}")
        assert result["success"] == False
        assert "Missing required" in result["error"]
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 8: Execute non-existent tool
    print("\n[TEST 8] Execute non-existent tool...")
    try:
        result = await executor.execute(
            "non_existent_tool",
            {}
        )
        print(f"  ✓ Result: {result}")
        assert result["success"] == False
        assert "not found" in result["error"]
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 9: Singleton pattern
    print("\n[TEST 9] Singleton pattern...")
    try:
        registry2 = get_tool_registry()
        executor2 = get_tool_executor()
        
        assert registry is registry2
        print(f"  ✓ Singleton working correctly")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 10: Health check
    print("\n[TEST 10] Health check...")
    try:
        health = await registry.health_check()
        print(f"  ✓ Health: {health}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
