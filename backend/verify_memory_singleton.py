from app.core.memory_manager import get_agent_memory

print("Requesting memory instance 1...")
m1 = get_agent_memory()
print(f"Got instance 1: {id(m1)}")

print("Requesting memory instance 2...")
m2 = get_agent_memory()
print(f"Got instance 2: {id(m2)}")

if m1 is m2:
    print("SUCCESS: Both instances are the same object (Singleton works).")
else:
    print("FAILURE: Instances are different.")
    exit(1)
