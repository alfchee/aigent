import asyncio
import os
from dotenv import load_dotenv
from google import genai

async def list_models():
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    client = genai.Client(api_key=api_key)
    print("Listing models...")
    try:
        # Use synchronous list to be safe if aio.models.list is buggy
        for model in client.models.list():
            print(f"- {model.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
