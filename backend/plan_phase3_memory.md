# Plan Fase 3: Memoria Híbrida y Selectiva

Este plan detalla la implementación de un sistema de memoria avanzado para NaviBot, combinando memoria de corto plazo (LangGraph State), memoria de largo plazo (Mem0) y recuperación selectiva (RAG) para optimizar latencia y precisión.

## Objetivos
1.  **Persistencia de Contexto**: Mantener el hilo de la conversación actual sin perder detalles.
2.  **Memoria de Usuario (Hechos)**: Recordar preferencias y datos clave del usuario a largo plazo usando Mem0.
3.  **Eficiencia (RAG Selectivo)**: Evitar búsquedas vectoriales innecesarias en cada interacción.

## Arquitectura Propuesta

### 1. Memoria de Corto Plazo (Short-Term Memory)
-   **Mecanismo**: `LangGraph State` + `SQLite`.
-   **Implementación**:
    -   Ya existe una base en `app/core/persistence.py` y `app/core/graph_state.py`.
    -   **Mejora**: Asegurar que el `State` de LangGraph se hidrate correctamente al inicio de cada turno con los últimos N mensajes de la sesión actual.
    -   **Acción**: Verificar y ajustar `load_chat_history` para que sea compatible con el esquema de mensajes de LangGraph (`BaseMessage`).

### 2. Memoria de Largo Plazo (Long-Term Memory con Mem0)
-   **Tecnología**: [Mem0](https://github.com/mem0ai/mem0) (Open Source).
-   **Función**: Extraer y almacenar "hechos" (facts) del usuario automáticamente.
    -   *Ejemplo*: "El usuario es desarrollador Python", "Prefiere respuestas concisas".
-   **Integración**:
    -   Reemplazar o extender `app/core/memory_manager.py`.
    -   Configurar Mem0 con un backend vectorial ligero (Qdrant local o ChromaDB existente).
    -   **Hook de Escritura**: Al finalizar un turno (o mediante una herramienta explícita), el agente puede decidir "memorizar" un hecho importante.
    -   **Hook de Lectura**: Al inicio de la sesión, cargar los "hechos" relevantes del usuario (User Profile) en el System Prompt.

### 3. RAG Selectivo (Selective Retrieval)
-   **Problema Actual**: Búsqueda vectorial indiscriminada o nula.
-   **Solución**: Herramienta `search_memory` explicita.
-   **Flujo**:
    1.  El usuario envía un mensaje.
    2.  El Agente (Planner) analiza si necesita información histórica.
    3.  **SI** necesita: Invoca la herramienta `search_memory(query)`.
    4.  **NO** necesita: Responde con el contexto actual y System Prompt.
-   **Ventaja**: Reduce latencia al no consultar vectores para "Hola" o "¿Qué hora es?".

## Pasos de Implementación

### Paso 1: Configuración de Entorno y Dependencias
-   [ ] Agregar `mem0ai` a `requirements.txt`.
-   [ ] Configurar variables de entorno para Mem0 (si usa vector store externo u OpenAI/Gemini para extracción).

### Paso 2: Integración de Mem0 (Backend)
-   [ ] Crear/Modificar `app/core/memory_manager.py`:
    -   Inicializar cliente `Memory` de Mem0.
    -   Implementar métodos `add_memory(text, user_id)` y `get_memories(user_id)`.
    -   Configurar para usar el modelo de embeddings local o API existente.

### Paso 3: Herramientas de Memoria para el Agente
-   [ ] Actualizar `app/skills/memory.py`:
    -   `save_fact(fact)`: Herramienta para que el agente guarde explícitamente un hecho.
    -   `recall_facts(query)`: Herramienta para buscar en la memoria a largo plazo.

### Paso 4: Optimización del System Prompt (RAG Selectivo)
-   [ ] Modificar `app/core/agent.py` -> `_build_system_instruction`:
    -   Inyectar automáticamente los "hechos" más relevantes del usuario (Top-K static facts) al inicio del prompt.
    -   Instruir al agente sobre cuándo usar `recall_facts` para búsquedas profundas.

### Paso 5: Validación
-   [ ] Test 1: Verificar que el agente recuerda un dato dado en una sesión anterior.
-   [ ] Test 2: Verificar que el agente NO busca en memoria para saludos simples (latencia baja).
-   [ ] Test 3: Verificar persistencia de hechos en Mem0.

## Archivos Afectados
-   `requirements.txt`
-   `app/core/memory_manager.py`
-   `app/skills/memory.py`
-   `app/core/agent.py`
