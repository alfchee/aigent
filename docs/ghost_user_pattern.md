# Ghost User Pattern for Scheduler Isolation

This document describes the Ghost User pattern implemented in NaviBot to ensure scheduled tasks run in isolated sessions without interfering with live user chats.

## Problem

When the Scheduler executes background tasks, it could potentially:
1. **Block DB sessions** used by live user conversations
2. **Access user memories** that should be private
3. **Cause race conditions** in concurrent session access

## Solution: Ghost User Pattern

The Ghost User pattern creates isolated execution contexts for automated scheduler tasks:

### Key Components

#### 1. Entity Type Classification

Located in [`backend/app/core/runtime_context.py`](backend/app/core/runtime_context.py):

```python
class EntityType(Enum):
    HUMAN = "human"
    SCHEDULER = "scheduler"
    API = "api"
    UNKNOWN = "unknown"
```

#### 2. Context Variables

```python
_entity_type_var: ContextVar[EntityType] = ContextVar("navibot_entity_type", default=EntityType.HUMAN)
_entity_metadata_var: ContextVar[dict] = ContextVar("navibot_entity_metadata", default={})
```

#### 3. Helper Functions

- `get_entity_type()` - Returns current entity type
- `set_entity_type(EntityType)` - Sets entity type for context
- `is_scheduler_entity()` - Checks if current context is a scheduler task
- `is_human_entity()` - Checks if current context is a human user

## How It Works

```
Human User Session          Scheduled Task
┌─────────────────┐        ┌─────────────────────┐
│ session_id:     │        │ ghost_session_id:   │
│ tg_12345       │        │ ghost_scheduler_abc │
│                 │        │                     │
│ entity_type:   │        │ entity_type:        │
│ HUMAN          │        │ SCHEDULER           │
│                 │        │                     │
│ memory_user_id:│        │ memory_user_id:     │
│ tg_12345       │        │ (isolated)         │
└─────────────────┘        └─────────────────────┘
```

### Session Isolation

In [`backend/app/core/scheduler_service.py`](backend/app/core/scheduler_service.py):

```python
# Generate ghost session ID for scheduler tasks
ghost_job_id = job_id or str(uuid.uuid4())[:8]
isolated_session_id = f"ghost_scheduler_{ghost_job_id}"

# Set entity type to SCHEDULER
set_entity_type(EntityType.SCHEDULER)

# Set entity metadata for auditing
set_entity_metadata({
    "job_id": ghost_job_id,
    "entity_type": "scheduler",
    "is_automated": True,
    "parent_session_id": session_id,
    "prompt": _truncate_text(prompt)
})
```

### Memory Separation

In [`backend/app/skills/memory.py`](backend/app/skills/memory.py):

```python
from app.core.runtime_context import is_scheduler_entity

def recall_facts(query: str, ...):
    # Prevent scheduler from reading human user memories
    if is_scheduler_entity():
        return "[Scheduler Task] Memory recall skipped - automated tasks cannot access user memories"
    
    # Normal memory recall for human users
    ...

def save_fact(fact: str, ...):
    # Prevent scheduler from writing to human user memories
    if is_scheduler_entity():
        return "[Scheduler Task] Memory save skipped - automated tasks cannot write to user memories"
    
    # Normal memory save for human users
    ...
```

## Benefits

| Benefit | Description |
|---------|-------------|
| **Complete Isolation** | Scheduler tasks use separate session IDs |
| **No DB Locking** | Prevents blocking of live user sessions |
| **Memory Protection** | Scheduler cannot access human user memories |
| **Auditing** | Entity metadata enables tracking automated vs human actions |
| **Resource Management** | System can distinguish automated interactions |

## Example Log Entry

```json
{
  "job_id": "abc-123",
  "ghost_session_id": "ghost_scheduler_abc-123",
  "entity_type": "scheduler",
  "is_automated": true,
  "parent_session_id": "tg_10018049",
  "prompt": "Generate daily report...",
  "status": "success",
  "execution_time_seconds": 45.2
}
```

## API Usage

The Scheduler can be invoked via the API:

```python
# Schedule a task
schedule_task(
    prompt="Generate daily report at 9 AM",
    execute_at="2026-02-20 09:00:00",
    use_react_loop=True,
    max_iterations=10
)
```

The task will execute with:
- `entity_type`: SCHEDULER
- `session_id`: `ghost_scheduler_{job_id}`
- No access to human user memories
