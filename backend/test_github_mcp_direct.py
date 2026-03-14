import os
import sys
import asyncio
from app.mcp_servers.github_enhanced import search_issues_and_prs

# Set env var for testing
os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "your_github_token_here"

def test_tool():
    print("Testing search_issues_and_prs...")
    query = "repo:getstandup/models-trainer is:issue updated:>2026-03-10"
    try:
        result = search_issues_and_prs(query=query)
        print(f"Result type: {type(result)}")
        print(f"Result prefix: {result[:100]}")
        if "Error" in result:
            print("Tool returned error!")
    except Exception as e:
        print(f"Exception calling tool: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tool()
