import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run():
    # Environment for the server
    env = os.environ.copy()
    env["GITHUB_PERSONAL_ACCESS_TOKEN"] = "your_github_token_here"
    env["PYTHONPATH"] = os.getcwd()

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.mcp_servers.github_enhanced"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Tools: {[t.name for t in tools.tools]}")

            # Call tool
            print("\nCalling search_issues_and_prs...")
            try:
                result = await session.call_tool(
                    "search_issues_and_prs",
                    arguments={
                        "query": "repo:getstandup/models-trainer is:issue updated:>2026-03-10",
                        "sort": "created",
                        "order": "desc",
                        "per_page": 5
                    }
                )
                print("Result:")
                for content in result.content:
                    print(content.text)
            except Exception as e:
                print(f"Error calling tool: {e}")

if __name__ == "__main__":
    asyncio.run(run())
