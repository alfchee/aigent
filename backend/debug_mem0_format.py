#!/usr/bin/env python3
"""
Script de diagnóstico para verificar el formato de respuesta de mem0.
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.memory_manager import get_agent_memory
from app.core.runtime_context import set_memory_user_id, reset_memory_user_id

def debug_mem0_format():
    """Debug the exact format returned by mem0.search()"""
    print("🔍 Debug: Analizando formato de respuesta de mem0...")
    
    test_user_id = "debug_user"
    test_query = "test format"
    
    token = set_memory_user_id(test_user_id)
    
    try:
        memory_manager = get_agent_memory()
        
        if memory_manager.memory is None:
            print("❌ Memory no inicializada")
            return
            
        print("\n1️⃣ Probando search() con query vacía...")
        try:
            result = memory_manager.memory.search(test_query, user_id=test_user_id, limit=3)
            print(f"📋 Tipo de resultado: {type(result)}")
            print(f"📊 Contenido: {result}")
            
            if isinstance(result, list):
                print(f"📏 Longitud: {len(result)}")
                if result:
                    print(f"🔍 Primer elemento tipo: {type(result[0])}")
                    print(f"🔍 Primer elemento: {result[0]}")
                    if isinstance(result[0], dict):
                        print(f"🔑 Claves: {list(result[0].keys())}")
            
        except Exception as e:
            print(f"❌ Error en search: {e}")
            import traceback
            traceback.print_exc()
            
        print("\n2️⃣ Probando get_all()...")
        try:
            all_facts = memory_manager.memory.get_all(user_id=test_user_id)
            print(f"📋 Tipo de all_facts: {type(all_facts)}")
            print(f"📊 Contenido: {all_facts}")
            
            if isinstance(all_facts, list):
                print(f"📏 Longitud: {len(all_facts)}")
                if all_facts:
                    print(f"🔍 Primer elemento: {all_facts[0]}")
                    if isinstance(all_facts[0], dict):
                        print(f"🔑 Claves: {list(all_facts[0].keys())}")
                        
        except Exception as e:
            print(f"❌ Error en get_all: {e}")
            import traceback
            traceback.print_exc()
            
    finally:
        reset_memory_user_id(token)

if __name__ == "__main__":
    debug_mem0_format()