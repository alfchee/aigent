import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Listando modelos con google-genai SDK:")
try:
    # El nuevo SDK usa client.models.list()
    # Paginator handling might be needed depending on SDK version, 
    # but usually iterating works.
    for model in client.models.list():
        print(f"- {model.name}")
except Exception as e:
    print(f"Error listing models: {e}")
