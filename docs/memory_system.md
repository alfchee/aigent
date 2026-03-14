# Sistema de Memoria Multi-Nivel

NaviBot implementa un sistema de memoria de múltiples niveles inspirado en el artículo [arxiv 2603.05344v1](https://arxiv.org/html/2603.05344v1), completamente agnóstico al proveedor de LLM.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryController                         │
│            (Interfaz Unificada - Provider Agnostic)        │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Working       │   │ Episodic      │   │ Semantic      │
│ Memory        │   │ Memory        │   │ Memory        │
│               │   │               │   │               │
│ - Ventana de  │   │ - SQLite      │   │ - Mem0        │
│   atención    │   │ - Historial   │   │ - Vector Store│
│ - In-memory   │   │   persistente │   │ - Facts       │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Global Context  │
                    │ (Preferencias)  │
                    └─────────────────┘
```

---

## Niveles de Memoria

### Nivel 1: Working Memory (Memoria de Trabajo)

Almacena el contexto inmediato de la conversación en memoria.

**Características:**
- Almacenamiento efímero (se pierde al reiniciar)
- Ventana deslizante de max 20 items por sesión
- Evicción FIFO automática
- Acceso más rápido

**Uso:**
```python
from app.core.memory import get_working_memory

wm = get_working_memory()
wm.add(item)  # Agregar item
context = wm.get_context_window(session_id)  # Obtener contexto
```

---

### Nivel 2: Episodic Memory (Memoria Episódica)

Persiste el historial de sesiones en SQLite.

**Características:**
- Almacenamiento persistente
- Historial completo de conversaciones
- Integración con la base de datos existente

**Uso:**
```python
from app.core.memory import get_episodic_memory

em = get_episodic_memory()
history = await em.get_session_history(session_id, limit=100)
```

---

### Nivel 3: Semantic Memory (Memoria Semántica)

Almacena hechos y conocimiento usando vector store (Mem0).

**Características:**
- Búsqueda semántica por similitud
- Persistente a través de sesiones
- Extracción automática de facts por IA

**Uso:**
```python
from app.core.memory import get_semantic_memory

sm = get_semantic_memory()
await sm.add_fact(user_id, "Usuario prefiere modo oscuro")
results = await sm.search(query, user_id, limit=5)
```

---

### Nivel 4: Global Context (Contexto Global)

Almacena preferencias del usuario cross-session.

**Características:**
- Preferencias persistentes
- Cache en memoria
- Acceso rápido

---

## Uso del Sistema

### Interfaz Unificada: MemoryController

```python
from app.core.memory import get_memory_controller

mc = get_memory_controller()

# Agregar mensaje (working + episodic)
await mc.add_message(session_id, user_id, "user", "Hola")

# Agregar fact (semantic)
await mc.add_fact(user_id, "Usuario: Me llamo Juan")

# Obtener contexto consolidado
context = await mc.get_context(session_id, user_id, "query actual")

# Convertir a formato para LLM
prompt_context = context.to_prompt_format()
```

### Funciones como Herramientas (Skills)

```python
from app.skills.memory import recall_facts, save_fact

# Recordar información
result = recall_facts("¿Cómo me llamo?")

# Guardar información
result = save_fact("Mi color favorito es azul")
```

---

## Cache de Contexto

El MemoryController implementa un sistema de cache para optimizar el rendimiento:

**Características:**
- TTL: 5 minutos (configurable)
- Invalidación automática al agregar mensajes
- Solo cachea consultas vacías

**Configuración:**
```python
# En controller.py
CONTEXT_CACHE_TTL_SECONDS = 300  # 5 minutos
```

---

## Migración desde el Sistema Legacy

### Antes (Legacy):
```python
from app.core.memory_manager import get_agent_memory

memory = get_agent_memory()
memory.add_interaction(user_id, text)
facts = memory.get_all_user_facts(user_id)
```

### Ahora (Nuevo):
```python
from app.core.memory import get_memory_controller

mc = get_memory_controller()
await mc.add_fact(user_id, text)
context = await mc.get_context(session_id, user_id, query)
```

---

## Proveedores Soportados

El sistema es **agnóstico al proveedor de LLM**. Currently supports:
- Google GenAI (Gemini)
- OpenRouter
- LM Studio
- OpenAI

La memoria funciona independientemente del proveedor usado.

---

## Integración con el Agente

El agente (`NaviBot`) usa el MemoryController automáticamente:

1. **Mensajes**: Se guardan en working + episodic memory
2. **Facts**: Se extraen automáticamente mediante regex
3. **Contexto**: Se recupera y se inyecta en el prompt del LLM

```python
# En agent.py
self.memory_controller = get_memory_controller()

# Después de procesar un mensaje
await self.memory_controller.add_message(session_id, user_id, role, content)

# Auto-extracción de facts
await self._extract_and_save_facts(session_id, user_message, assistant_response)
```

---

## Auto-extracción de Facts

El sistema detecta automáticamente información personal en los mensajes:

| Tipo | Patrones |
|------|----------|
| Nombre | me llamo, mi nombre es, me dicen |
| Preferencia | prefiero, me gusta, me encanta |
| Disgusto | no me gusta, odio |
| Ubicación | vivo en, estoy en |
| Trabajo | trabajo en, trabajo como |

---

## Configuración

### Mem0 (Semantic Memory)

Configuración en `memory_manager.py`:
```python
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": "./navi_memory_qdrant",
            "embedding_model_dims": 768
        }
    },
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.0-flash",
            "api_key": os.getenv("GOOGLE_API_KEY")
        }
    }
}
```

---

## Limpieza (Shutdown)

```python
# En main.py
from app.core.memory_manager import cleanup_memory

cleanup_memory()  # Limpia recursos de Mem0
```
