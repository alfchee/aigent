# Fase 2 Backend: Memoria + Sandboxing Pydantic/Monty

## Implementado

### 1. Sandboxing Pydantic/Monty
- Se reemplazó el enfoque E2B por un pipeline validado con Pydantic y Monty en `app/sandbox/e2b_sandbox.py`.
- Se añadieron modelos:
  - `SandboxLimits`
  - `SandboxConfig`
  - `CodeExecutionRequest`
  - `CodeExecutionResult`
- Se aplican políticas de seguridad:
  - límite de longitud de código,
  - timeout de ejecución,
  - bloqueo de patrones peligrosos (`os`, `subprocess`, `socket`, `eval`, `exec`, `open`, `__import__`),
  - truncado de salida para proteger memoria.
- Se ejecuta código con `python -I -c` en directorio aislado por `session_id`.
- Se usa `monty.json.jsanitize` para sanitizar metadatos de artefactos.
- Se añadieron perfiles por rol con límites diferenciados (`default`, `coder`, `researcher`).
- Se añadieron límites de recursos del proceso (`CPU`, `memoria`, `tamaño de archivo`, `NPROC`, `NOFILE`).
- Se añadió allowlist de imports por rol con validación estática del AST.
- Se añadieron métricas de ejecución por rol y globales.

### 2. Integración en flujo WebSocket
- Se integró sandbox en `app/main.py`.
- El backend:
  - emite eventos de estado (`type: status`) y de herramienta (`type: tool_call`),
  - detecta ejecución de código con `/python ...` o bloque ```python ... ```,
  - ejecuta en sandbox validado y devuelve salida al cliente.

### 3. Memoria episódica y semántica
- Se añadieron módulos:
  - `app/memory/episodic.py` (SQLite para resúmenes por sesión),
  - `app/memory/semantic.py` (capa semántica con fallback local),
  - `app/memory/controller.py` (controlador unificado).
- Se corrigió y simplificó `app/memory/openviking_store.py`.
- Se integra memoria en `app/main.py`:
  - guarda hechos por sesión,
  - inyecta contexto semántico en prompts,
  - persiste resumen episódico periódico.
- Se habilitó versionado de resúmenes episódicos y consulta por ventana temporal.

### 4. Integración AgentGraph en runtime
- Se activó `AgentGraph` para respuestas de chat no orientadas a ejecución de código.
- Se mantiene fallback a `default_llm` si el grafo falla.
- Se conserva el canal WebSocket con eventos de estado y herramientas.

### 5. Observabilidad y endpoints operativos
- Endpoint de métricas de sandbox: `GET /sandbox/metrics`.
- Endpoint de resúmenes episódicos por rango:
  - `GET /memory/{session_id}/summaries?since_ts=<unix>&limit=<n>`.
- Soporte de consulta temporal para memoria episódica versionada.

## Dependencias
- `requirements.txt` actualizado:
  - eliminado `e2b`,
  - añadido `monty`.

## Validación
- Pruebas ejecutadas con éxito:
  - `PYTHONPATH=backend pytest -q backend/tests` → 16 passed.
- Verificación sintáctica:
  - `python -m py_compile` sobre módulos modificados.
