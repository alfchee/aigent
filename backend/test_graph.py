import os
import sys
import asyncio

# Añadir directorio actual al path
sys.path.append(os.getcwd())

from langchain_core.messages import HumanMessage
from app.core.agent_graph import AgentGraph

async def test_agent_graph():
    print("🚀 Inicializando Grafo del Agente...")
    try:
        # Usamos un modelo validado por el script check_models_new_sdk.py
        agent_graph = AgentGraph(model_name="gemini-2.0-flash") 
        graph = agent_graph.get_runnable()
        print("✅ Grafo compilado correctamente.")
    except Exception as e:
        print(f"❌ Error al inicializar grafo: {e}")
        return

    # Mensaje de prueba específico para probar enrutamiento
    user_input = "Quiero agendar una reunión mañana a las 10am con el equipo de ventas."
    print(f"\n👤 Usuario: {user_input}")
    
    # Ejecutar el grafo
    try:
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
        # Ejecución paso a paso para ver qué nodos se activan
        async for event in graph.astream(inputs, stream_mode="updates"):
            for node, values in event.items():
                print(f"🔄 Nodo ejecutado: {node}")
                
                # Si es el supervisor, mostrar a dónde enrutó
                if node == "supervisor":
                    print(f"   🚦 Supervisor decidió: {values.get('next')}")
                
                if 'messages' in values:
                    last_msg = values['messages'][-1]
                    print(f"   Mensaje ({last_msg.name if hasattr(last_msg, 'name') else 'Agent'}): {last_msg.content[:100]}...")

        print("\n✅ Prueba finalizada.")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_graph())
