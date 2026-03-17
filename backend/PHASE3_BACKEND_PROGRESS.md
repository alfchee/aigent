# Fase 3 Backend: Roles, WebSocket y Telegram

## Implementado

### 1. Roles dinámicos
- Se fortaleció `RoleManager` con:
  - `snapshot()` para inspección operativa,
  - `reload()` para recarga en caliente de `roles.json`,
  - `role_for_skill()` para resolver worker por skill.
- Se normalizan skills por worker para evitar duplicados.

### 2. WebSocket manager robusto
- Se mejoró el `ConnectionManager`:
  - limpieza automática de conexiones caídas durante envío,
  - `active_count(session_id)` para observabilidad.

### 3. Canal Telegram conectado al runtime real
- `handle_text` ahora:
  - guarda memoria de conversación,
  - ejecuta sandbox para `/python`,
  - usa `AgentGraph` para respuestas normales,
  - aplica fallback a `default_llm` ante error.
- `handle_media` guarda archivos en `workspace/sessions/{chat_id}/downloads`
  y registra el evento en memoria.

### 4. Endpoints operativos de Fase 3
- `GET /roles`: snapshot completo de supervisor/workers activos.
- `POST /roles/reload`: recarga dinámica de roles.
- Se mantienen endpoints de Fase 2 (`/sandbox/metrics`, `/memory/{session_id}/summaries`).

## Pruebas
- Nuevas pruebas:
  - `test_roles_manager.py`
  - `test_websocket_manager.py`
- Estado suite backend:
  - `PYTHONPATH=backend pytest -q backend/tests` → `19 passed`.
