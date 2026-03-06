import asyncio
import os
import sys
import json
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.core.agent import NaviBot
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("Initializing NaviBot...")
    # Mock API Key if missing (for CI/CD or no-env situations)
    if not os.getenv("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY missing. Mocking client for basic structure test.")
        # This won't test the actual API interaction, which is what we need.
        # But let's assume the user has it set in their env.
        pass

    agent = NaviBot()
    
    # Verify MCP loading
    print("Loading MCP servers...")
    await agent.mcp_manager.load_servers()
    tools = await agent.mcp_manager.get_all_tools()
    print(f"Loaded {len(tools)} MCP tools.")
    for t in tools:
        print(f" - {t['name']}")

    # Test Chat
    session_id = "test-mcp-session-manual"
    query = "Busca repositorios de 'mcp-python' en github"
    
    print(f"\nSending message: '{query}'")
    try:
        response = await agent.send_message(query)
        print("\n--- Final Response (Github) ---")
        print(response)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    # Test Filesystem
    query_fs = "List files in /tmp"
    print(f"\nSending message: '{query_fs}'")
    try:
        response = await agent.send_message(query_fs)
        print("\n--- Final Response (Filesystem) ---")
        print(response)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    # Clean up
    await agent.mcp_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
