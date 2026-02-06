import asyncio
import os
from dotenv import load_dotenv
from app.core.agent import NaviBot

async def test_agent():
    load_dotenv()
    print(f"Testing agent with API KEY: {os.getenv('GOOGLE_API_KEY')[:10]}...")
    bot = NaviBot()
    try:
        response = await bot.send_message("Hola, respond with 'OK' if you see this.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent())
