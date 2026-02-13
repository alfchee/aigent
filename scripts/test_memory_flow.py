import sys
import os
import time

# Add backend to path to allow imports from app
# Assuming this script is run from the project root
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.memory_manager import get_agent_memory
except ImportError:
    # Fallback if run from scripts directory directly
    sys.path.append(os.path.join(os.getcwd(), '../backend'))
    from app.core.memory_manager import get_agent_memory

def test_memory_flow():
    print("🚀 Initializing Memory System...")
    memory = get_agent_memory()
    
    user_id = "test_user_preferences"
    # SAFE EXAMPLE: User preferences instead of secrets
    fact = "The user prefers to use Python for backend development and React for frontend."
    
    print(f"\n1. Storing memory: '{fact}'...")
    success = memory.add_interaction(user_id, fact)
    
    if success:
        print("✅ Memory stored successfully.")
    else:
        print("❌ Failed to store memory.")
        return

    # Allow a brief moment for persistence/indexing if needed (usually immediate for local)
    time.sleep(1)
    
    query = "What represents the user's preferred tech stack?"
    print(f"\n2. Searching for: '{query}'...")
    
    # Retrieve relevant context
    context = memory.get_relevant_context(user_id, query)
    
    print(f"\n3. Retrieved Context:\n{context}")
    
    if "Python" in context and "React" in context:
        print("\n✅ SUCCESS: Relevant preferences found!")
    else:
        print("\n❌ FAILURE: Could not retrieve the specific preferences.")

if __name__ == "__main__":
    test_memory_flow()
