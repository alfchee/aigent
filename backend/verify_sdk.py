from google import genai
try:
    from google.genai import types
    print("Types module found")
except ImportError:
    print("Types module NOT found")

client = genai.Client(api_key="TEST")
print(f"Client methods: {dir(client)}")

if hasattr(client, 'aio'):
    print(f"Async client found: {client.aio}")
    print(f"Async chats methods: {dir(client.aio.chats)}")
else:
    print("Async client NOT found on client.aio")
