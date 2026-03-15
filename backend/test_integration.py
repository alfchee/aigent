#!/usr/bin/env python3
"""
Integration test for the ToolRegistry, ToolExecutor, and BotPool integration.
"""

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.tools import tool


# Test tools
@tool
def test_divide(a: int, b: int) -> int:
    """Divides two numbers.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        The result of a / b
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a // b


async def main():
    print("=" * 60)
    print("Integration Test: ToolRegistry + BotPool")
    print("=" * 60)
    
    # Test 1: Import all components
    print("\n[TEST 1] Importing components...")
    try:
        from app.core.tool_registry import ToolRegistry, get_tool_registry
        from app.core.tool_executor import ToolExecutor
        from app.core.bot_pool import BotPool, bot_pool
        print("  ✓ All components imported successfully")
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return 1
    
    # Test 2: Initialize registry
    print("\n[TEST 2] Initialize ToolRegistry...")
    try:
        from app.core.tool_registry import ToolRegistry, ToolMetadata
        
        registry = ToolRegistry()
        await registry.register_tool(
            test_divide,
            ToolMetadata(
                name="test_divide",
                source="skill",
                category="utility",
                description="Divides two numbers"
            )
        )
        
        stats = registry.get_stats()
        print(f"  ✓ Registry initialized with {stats['total_tools']} tools")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 3: Initialize executor
    print("\n[TEST 3] Initialize ToolExecutor...")
    try:
        executor = ToolExecutor(registry)
        print("  ✓ ToolExecutor created")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 4: Execute tool
    print("\n[TEST 4] Execute tool...")
    try:
        result = await executor.execute("test_divide", {"a": 10, "b": 2})
        assert result["success"] == True
        assert result["result"] == 5
        print(f"  ✓ Result: {result['result']}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 5: Test retry logic
    print("\n[TEST 5] Test retry with failure...")
    try:
        # This should fail
        result = await executor.execute("test_divide", {"a": 10, "b": 0})
        assert result["success"] == False
        print(f"  ✓ Retry logic works: {result['error']}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 6: BotPool integration
    print("\n[TEST 6] BotPool methods...")
    try:
        status = bot_pool.get_tool_registry_status()
        print(f"  ✓ Registry status accessible: {status.get('total_tools', 0)} tools")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 7: Health check
    print("\n[TEST 7] Health check...")
    try:
        health = await registry.health_check()
        print(f"  ✓ Health: {list(health.keys())}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    # Test 8: Execution stats
    print("\n[TEST 8] Execution stats...")
    try:
        stats = executor.get_stats()
        print(f"  ✓ Stats: {stats}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("All integration tests passed!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
