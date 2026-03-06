#!/usr/bin/env python3
"""
Script de diagnóstico corregido para verificar el funcionamiento de la memoria persistente.
"""
import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.memory_manager import get_agent_memory
from app.core.runtime_context import set_memory_user_id, reset_memory_user_id

def test_memory_persistence():
    """Test complete memory persistence cycle"""
    print("🧪 Iniciando prueba de diagnóstico de memoria...")
    
    # Test user ID
    test_user_id = "test_user_diagnostic"
    test_query = "anime favorito"
    test_fact = "Mi anime favorito es Attack on Titan"
    
    print(f"📋 Usuario de prueba: {test_user_id}")
    print(f"💭 Hecho a guardar: {test_fact}")
    
    # Set user context
    token = set_memory_user_id(test_user_id)
    
    try:
        # Get memory manager
        print("\n1️⃣ Obteniendo manager de memoria...")
        memory_manager = get_agent_memory()
        
        if memory_manager.memory is None:
            print("❌ ERROR: Memory manager no está inicializado")
            return False
            
        print("✅ Memory manager obtenido correctamente")
        
        # Search before saving
        print(f"\n2️⃣ Buscando recuerdos previos sobre '{test_query}'...")
        memories_before = memory_manager.get_relevant_context(test_user_id, test_query)
        print(f"📊 Recuerdos encontrados antes: {len(memories_before)} caracteres")
        if memories_before:
            print(f"📝 Contenido: {memories_before[:100]}...")
        
        # Save new fact
        print(f"\n3️⃣ Guardando hecho: '{test_fact}'...")
        save_result = memory_manager.add_interaction(test_user_id, test_fact)
        
        if not save_result:
            print("❌ ERROR: No se pudo guardar el hecho")
            return False
            
        print("✅ Hecho guardado exitosamente")
        
        # Wait a moment for persistence
        print("\n4️⃣ Esperando persistencia...")
        time.sleep(1)
        
        # Search after saving
        print(f"\n5️⃣ Buscando recuerdos después sobre '{test_query}'...")
        memories_after = memory_manager.get_relevant_context(test_user_id, test_query)
        print(f"📊 Recuerdos encontrados después: {len(memories_after)} caracteres")
        
        # Check if we found the memory (considering that mem0 rephrases)
        if memories_after and ("Attack on Titan" in memories_after or "anime" in memories_after):
            print("✅ ÉXITO: Se encontró información relevante sobre el anime")
            
            # Test retrieval by getting all facts
            print("\n6️⃣ Obteniendo todos los hechos del usuario...")
            all_facts = memory_manager.get_all_user_facts(test_user_id)
            print(f"📊 Total de hechos: {len(all_facts)}")
            
            # Look for Attack on Titan in any fact
            found_titan = any("Attack on Titan" in str(fact) or "anime" in str(fact) for fact in all_facts)
            if found_titan:
                print("✅ ÉXITO: Hecho encontrado en lista completa")
                return True
            else:
                print("⚠️  ADVERTENCIA: Hecho no encontrado en lista completa")
                print(f"📋 Todos los hechos: {all_facts}")
                return False
        else:
            print("❌ ERROR: No se encontró información relevante")
            print(f"📝 Contenido actual: {memories_after}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        reset_memory_user_id(token)

def test_cross_session():
    """Test memory across different sessions"""
    print("\n" + "="*60)
    print("🔄 Probando persistencia entre sesiones...")
    
    # First session
    print("\n📱 Simulando sesión de Telegram...")
    tg_user_id = "tg_user_123"
    tg_fact = "Usuario prefiere respuestas en español"
    
    tg_token = set_memory_user_id(tg_user_id)
    try:
        memory_manager = get_agent_memory()
        if memory_manager.memory:
            memory_manager.add_interaction(tg_user_id, tg_fact)
            print(f"✅ Guardado en Telegram: {tg_fact}")
        reset_memory_user_id(tg_token)
    except Exception as e:
        print(f"❌ Error en sesión Telegram: {e}")
        return False
    
    # Second session  
    print("\n🌐 Simulando sesión web...")
    web_user_id = "tg_user_123"  # Same user ID for cross-platform
    web_query = "idioma preferido"
    
    web_token = set_memory_user_id(web_user_id)
    try:
        memory_manager = get_agent_memory()
        if memory_manager.memory:
            result = memory_manager.get_relevant_context(web_user_id, web_query)
            # Check if we found something about language preference
            if result and ("español" in result or "idioma" in result or "preferencia" in result):
                print("✅ ÉXITO: Memoria compartida entre Telegram y Web")
                print(f"📝 Encontrado: {result}")
                return True
            else:
                print("❌ FALLA: No se encontró memoria entre plataformas")
                print(f"📝 Resultado: {result}")
                return False
        reset_memory_user_id(web_token)
    except Exception as e:
        print(f"❌ Error en sesión web: {e}")
        return False

if __name__ == "__main__":
    print("🧪 DIAGNÓSTICO DE MEMORIA PERSISTENTE")
    print("="*60)
    
    # Test 1: Basic persistence
    basic_success = test_memory_persistence()
    
    # Test 2: Cross-session
    cross_success = test_cross_session()
    
    # Summary
    print("\n" + "="*60)
    print("📊 RESUMEN DE PRUEBAS:")
    print(f"✅ Persistencia básica: {'PASÓ' if basic_success else 'FALLÓ'}")
    print(f"✅ Memoria cruzada: {'PASÓ' if cross_success else 'FALLÓ'}")
    
    if basic_success and cross_success:
        print("\n🎉 ¡Todas las pruebas pasaron! La memoria está funcionando correctamente.")
        sys.exit(0)
    else:
        print("\n❌ Algunas pruebas fallaron. Revisa los logs anteriores para detalles.")
        sys.exit(1)