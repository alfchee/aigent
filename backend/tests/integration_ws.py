import asyncio
import websockets
import json
import uuid
import sys

async def test_websocket_integration():
    session_id = f"test_client_{uuid.uuid4()}"
    uri = f"ws://127.0.0.1:8231/api/ws/chat/{session_id}"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Wait for connection ack
            ack = await websocket.recv()
            print(f"< {ack}")
            ack_data = json.loads(ack)
            if ack_data.get("type") != "connection.ack":
                print("Failed to receive connection ack")
                return False

            # Send a test message
            msg_id = str(uuid.uuid4())
            message = {
                "type": "chat.message",
                "id": msg_id,
                "content": "Hello, this is a test message. Please respond briefly."
            }
            print(f"> Sending: {message['content']}")
            await websocket.send(json.dumps(message))
            
            # Receive stream
            print("Receiving stream...")
            received_tokens = []
            final_response = None
            
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    msg_type = data.get("type")
                    
                    if msg_type == "agent.token":
                        content = data.get("data", {}).get("content", "")
                        received_tokens.append(content)
                        sys.stdout.write(content)
                        sys.stdout.flush()
                    
                    elif msg_type == "agent.response":
                        print("\n< Final Response Received")
                        final_response = data
                        break
                    
                    elif msg_type == "error":
                        print(f"\nError received: {data}")
                        return False
                        
                except asyncio.TimeoutError:
                    print("\nTimeout waiting for response")
                    return False
            
            if final_response and final_response.get("data", {}).get("done"):
                print("\nTest Passed: Full response received.")
                return True
            else:
                print("\nTest Failed: Incomplete response.")
                return False

    except Exception as e:
        print(f"\nConnection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_websocket_integration())
    sys.exit(0 if success else 1)
