import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.memory import save_memory, recall_memory

def test_memory():
    user_id = "test_user_123"
    fact = "La clave del servidor es 5544"
    
    print(f"1. Guardando memoria: '{fact}'...")
    save_memory(user_id, fact, source="test_script")
    
    query = "Cual es la clave del servidor?"
    print(f"2. Buscando: '{query}'...")
    results = recall_memory(user_id, query)
    
    print(f"3. Resultados: {results}")
    
    if any(fact in r for r in results):
        print("✅ SUCCESS: Memoria encontrada!")
    else:
        print("❌ FAILURE: Memoria no encontrada.")

if __name__ == "__main__":
    test_memory()
