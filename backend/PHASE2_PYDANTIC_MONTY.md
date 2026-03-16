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

## Dependencias
- `requirements.txt` actualizado:
  - eliminado `e2b`,
  - añadido `monty`.

## Validación
- Pruebas ejecutadas con éxito:
  - `PYTHONPATH=backend pytest -q backend/tests` → 12 passed.
- Verificación sintáctica:
  - `python -m py_compile` sobre módulos modificados.
