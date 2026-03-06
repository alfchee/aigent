# Scheduler Module

## Overview

The Scheduler module enables NaviBot to execute background tasks at specified times or intervals. Tasks are executed in isolated "ghost" sessions to prevent interference with live user conversations.

## Architecture

### Components

| Component | Location | Description |
|-----------|----------|-------------|
| **Scheduler Service** | `backend/app/core/scheduler_service.py` | Core scheduling logic using APScheduler |
| **Runtime Context** | `backend/app/core/runtime_context.py` | Entity type tracking (Human vs Scheduler) |
| **Memory Skills** | `backend/app/skills/memory.py` | Memory isolation checks |

### Ghost User Pattern

The scheduler uses a **Ghost User Pattern** to ensure isolation:

1. **Isolated Session IDs**: `ghost_scheduler_{job_id}` - completely separate from human sessions
2. **Entity Type Tracking**: `EntityType.SCHEDULER` marks all automated tasks
3. **Memory Separation**: Scheduler tasks cannot read/write human user memories

### Persistence

- **Database**: SQLite (`scheduler.db`) for job persistence
- **Job Types**:
  - **Date-based**: One-off execution at specific ISO timestamp
  - **Interval-based**: Recurring execution every N seconds
  - **Cron-based**: Cron expression support

## API

### Schedule a Task

```python
schedule_task(
    prompt: str,           # Task instruction
    execute_at: str,      # ISO timestamp "YYYY-MM-DD HH:MM:SS"
    session_id: str,      # Original session (for reference)
    use_react_loop: bool, # Enable ReAct loop
    max_iterations: int  # Max ReAct iterations
)
```

### Schedule Interval Task

```python
schedule_interval_task(
    prompt: str,           # Task instruction
    interval_seconds: int, # Interval in seconds
    session_id: str,
    use_react_loop: bool,
    max_iterations: int
)
```

## Entity Types

| Type | Description | Memory Access |
|------|-------------|---------------|
| `HUMAN` | Live user conversation | Full access |
| `SCHEDULER` | Automated scheduled task | No access (isolated) |
| `API` | Direct API call | Configurable |
| `UNKNOWN` | Unidentified | Restricted |

## Logging

All scheduler executions are logged with:

```json
{
  "job_id": "abc-123",
  "ghost_session_id": "ghost_scheduler_abc-123",
  "entity_type": "scheduler",
  "is_automated": true,
  "parent_session_id": "tg_10018049",
  "status": "success",
  "execution_time_seconds": 45.2
}
```

## Frontend Integration

The frontend uses:
- **Pinia Store**: Centralizes job state with stable hashes
- **Debounce + Retry**: Limits API calls with exponential backoff
- **Selective UI**: Virtual scrolling and fade transitions

### Store Location
- `frontend/src/stores/schedulerStore.ts`

### View Location
- `frontend/src/views/SchedulerView.vue`
