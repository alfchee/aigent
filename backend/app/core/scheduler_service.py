import asyncio
import json
import os
import time
import traceback
import uuid
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# We will import NaviBot lazily or inside the function to avoid circular imports if possible,
# but since agent.py imports skills inside __init__, top level import might be safe.
# However, to be safe and clean, we'll import inside the execution function or use a factory.

scheduler = None

def _get_logs_path():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "app/settings/scheduler_logs.jsonl")

def _append_log(entry: dict):
    path = _get_logs_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _read_logs() -> list[dict]:
    path = _get_logs_path()
    if not os.path.exists(path):
        return []
    logs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    logs.append(obj)
            except Exception:
                continue
    return logs

def _truncate_text(value: str, limit: int = 800) -> str:
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit]

def get_scheduler():
    global scheduler
    if scheduler is None:
        # Ensure the directory exists for the sqlite DB
        db_path = "sqlite:///scheduler.db"
        
        jobstores = {
            'default': SQLAlchemyJobStore(url=db_path)
        }
        scheduler = AsyncIOScheduler(jobstores=jobstores)
    return scheduler

async def execute_agent_task(
    prompt: str,
    session_id: str = "default",
    use_react_loop: bool = True,
    max_iterations: int = 10,
    timeout_seconds: int = 300,
    job_id: str | None = None
):
    """
    Execute an agent task with optional ReAct loop.
    
    GHOST USER PATTERN: Uses isolated session_id and entity metadata for scheduler tasks.
    This ensures:
    - Complete isolation from human user sessions
    - No DB locking conflicts with live chat sessions
    - Proper auditing of automated vs human interactions
    
    Args:
        prompt: The task prompt for the agent
        use_react_loop: Whether to use ReAct loop (default: True)
        max_iterations: Max reasoning cycles for ReAct (default: 10)
        timeout_seconds: Max execution time for ReAct (default: 300s)
    """
    print(f"\n{'='*60}")
    print(f"Executing scheduled task: {prompt}")
    print(f"ReAct Loop: {'Enabled' if use_react_loop else 'Disabled'}")
    print(f"{'='*60}\n")
    
    from app.core.agent import NaviBot
    from app.core.runtime_context import (
        reset_event_callback,
        reset_session_id,
        set_event_callback,
        set_session_id,
        set_entity_type,
        set_entity_metadata,
        reset_entity_type,
        reset_entity_metadata,
        EntityType
    )
    
    start_time = time.time()
    status = "success"
    response_text = ""
    error_text = ""
    error_trace = ""
    
    # GHOST USER PATTERN: Generate unique isolated session_id for scheduler
    # Format: ghost_scheduler_{job_id} or scheduled_{timestamp}_{session_id}
    ghost_job_id = job_id or str(uuid.uuid4())
    isolated_session_id = f"ghost_scheduler_{ghost_job_id}"
    
    # Store tokens for proper cleanup
    session_token = None
    callback_token = None
    entity_type_token = None
    entity_metadata_token = None
    
    try:
        # GHOST USER: Set scheduler entity type to identify non-human execution
        session_token = set_session_id(isolated_session_id)
        entity_type_token = set_entity_type(EntityType.SCHEDULER)
        entity_metadata_token = set_entity_metadata({
            "job_id": ghost_job_id,
            "entity_type": "scheduler",
            "is_automated": True,
            "parent_session_id": session_id,
            "prompt": prompt[:100],  # Store truncated prompt for debugging
            "use_react_loop": use_react_loop
        })
        callback_token = set_event_callback(None)
        
        # Instantiate a fresh agent for this task
        bot = NaviBot()
        
        # Ensure the session exists for the isolated thread
        await bot.ensure_session(isolated_session_id)
        
        if use_react_loop:
            # Use ReAct loop for autonomous multi-turn execution
            result = await bot.send_message_with_react(
                prompt,
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds
            )
            response_text = str(result.get("response", ""))
            
            print(f"\n{'='*60}")
            print(f"Task Execution Complete")
            print(f"Iterations: {result['iterations']}")
            print(f"Termination: {result['termination_reason']}")
            print(f"Execution Time: {result['execution_time_seconds']}s")
            print(f"{'='*60}")
            print(f"Final Response: {result['response']}")
            print(f"{'='*60}\n")
            
            if result.get('reasoning_trace'):
                print("\nReasoning Trace:")
                for trace_line in result['reasoning_trace']:
                    print(trace_line)
        else:
            response = await bot.send_message(prompt)
            response_text = str(response)
            print(f"\n{'='*60}")
            print(f"Task Execution Result: {response}")
            print(f"{'='*60}\n")
            
    except Exception as e:
        status = "error"
        error_text = f"{type(e).__name__}: {e}"
        error_trace = traceback.format_exc()
        print(f"\n{'='*60}")
        print(f"Error executing task: {e}")
        print(f"{'='*60}\n")
    finally:
        finished_at = time.time()
        _append_log({
            "job_id": job_id,
            "ghost_session_id": isolated_session_id,
            "prompt": prompt,
            "session_id": session_id,
            "entity_type": "scheduler",
            "is_automated": True,
            "use_react_loop": use_react_loop,
            "max_iterations": max_iterations,
            "status": status,
            "response": _truncate_text(response_text),
            "error": _truncate_text(error_text),
            "error_trace": _truncate_text(error_trace, 1600),
            "started_at": datetime.fromtimestamp(start_time).isoformat(),
            "finished_at": datetime.fromtimestamp(finished_at).isoformat(),
            "duration_seconds": round(finished_at - start_time, 3)
        })
        try:
            # Clean up context variables to prevent leaks
            if session_token:
                reset_session_id(session_token)
            if callback_token:
                reset_event_callback(callback_token)
            if entity_type_token:
                reset_entity_type(entity_type_token)
            if entity_metadata_token:
                reset_entity_metadata(entity_metadata_token)
        except Exception:
            pass


def start_scheduler():
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        print("Scheduler started with persistent storage.")

def schedule_task(prompt: str, execute_at: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a one-off task.
    
    Args:
        prompt: The task prompt
        execute_at: ISO format timestamp (YYYY-MM-DD HH:MM:SS)
        use_react_loop: Whether to use ReAct loop (default: True)
        max_iterations: Max reasoning cycles (default: 10)
    """
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    try:
        run_date = datetime.fromisoformat(execute_at)
        job_id = str(uuid.uuid4())
        sched.add_job(
            execute_agent_task, 
            DateTrigger(run_date=run_date), 
            id=job_id,
            name=prompt,
            args=[prompt, session_id, use_react_loop, max_iterations, 300, job_id]
        )
        mode = "ReAct loop" if use_react_loop else "simple"
        return f"Task '{prompt}' scheduled for {execute_at} ({mode} mode). Job ID: {job_id}"
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD HH:MM:SS"
    except Exception as e:
        return f"Error scheduling task: {str(e)}"

def schedule_interval_task(prompt: str, interval_seconds: int, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a recurring task.
    
    Args:
        prompt: The task prompt
        interval_seconds: Interval between executions
        use_react_loop: Whether to use ReAct loop (default: True)
        max_iterations: Max reasoning cycles (default: 10)
    """
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    try:
        job_id = str(uuid.uuid4())
        sched.add_job(
            execute_agent_task, 
            IntervalTrigger(seconds=interval_seconds), 
            id=job_id,
            name=prompt,
            args=[prompt, session_id, use_react_loop, max_iterations, 300, job_id]
        )
        mode = "ReAct loop" if use_react_loop else "simple"
        return f"Task '{prompt}' scheduled every {interval_seconds} seconds ({mode} mode). Job ID: {job_id}"
    except Exception as e:
        return f"Error scheduling task: {str(e)}"

def schedule_cron_task(prompt: str, cron: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    try:
        trigger = CronTrigger.from_crontab(cron)
        job_id = str(uuid.uuid4())
        sched.add_job(
            execute_agent_task,
            trigger,
            id=job_id,
            name=prompt,
            args=[prompt, session_id, use_react_loop, max_iterations, 300, job_id]
        )
        mode = "ReAct loop" if use_react_loop else "simple"
        return f"Task '{prompt}' scheduled with cron '{cron}' ({mode} mode). Job ID: {job_id}"
    except Exception as e:
        return f"Error scheduling cron task: {str(e)}"

def _serialize_trigger(trigger):
    if isinstance(trigger, DateTrigger):
        return {
            "type": "date",
            "run_date": trigger.run_date.isoformat() if trigger.run_date else None
        }
    if isinstance(trigger, IntervalTrigger):
        seconds = int(trigger.interval.total_seconds())
        return {
            "type": "interval",
            "seconds": seconds
        }
    if isinstance(trigger, CronTrigger):
        fields = {field.name: str(field) for field in trigger.fields}
        return {
            "type": "cron",
            "fields": fields
        }
    return {"type": "unknown", "repr": str(trigger)}

def list_jobs():
    sched = get_scheduler()
    logs = _read_logs()
    last_run_by_job = {}
    for log in logs:
        job_id = log.get("job_id")
        finished_at = log.get("finished_at")
        if not job_id or not finished_at:
            continue
        last_run_by_job[job_id] = finished_at
    jobs = []
    for job in sched.get_jobs():
        trigger_data = _serialize_trigger(job.trigger)
        args = list(job.args) if job.args else []
        prompt = args[0] if len(args) > 0 else ""
        session_id = args[1] if len(args) > 1 else "default"
        use_react_loop = args[2] if len(args) > 2 else True
        max_iterations = args[3] if len(args) > 3 else 10
        jobs.append({
            "id": job.id,
            "name": job.name or prompt or job.id,
            "prompt": prompt,
            "session_id": session_id,
            "use_react_loop": use_react_loop,
            "max_iterations": max_iterations,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "last_run_time": last_run_by_job.get(job.id),
            "trigger": trigger_data,
            "paused": job.next_run_time is None
        })
    return jobs

def get_job(job_id: str):
    sched = get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        return None
    logs = _read_logs()
    last_run_time = None
    for log in reversed(logs):
        if log.get("job_id") == job_id:
            last_run_time = log.get("finished_at")
            break
    trigger_data = _serialize_trigger(job.trigger)
    args = list(job.args) if job.args else []
    prompt = args[0] if len(args) > 0 else ""
    session_id = args[1] if len(args) > 1 else "default"
    use_react_loop = args[2] if len(args) > 2 else True
    max_iterations = args[3] if len(args) > 3 else 10
    return {
        "id": job.id,
        "name": job.name or prompt or job.id,
        "prompt": prompt,
        "session_id": session_id,
        "use_react_loop": use_react_loop,
        "max_iterations": max_iterations,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "last_run_time": last_run_time,
        "trigger": trigger_data,
        "paused": job.next_run_time is None
    }

def list_logs(job_id: str | None = None, limit: int = 200):
    logs = _read_logs()
    if job_id:
        logs = [log for log in logs if log.get("job_id") == job_id]
    return logs[-limit:]

def delete_job(job_id: str):
    """
    Elimina una tarea programada por su ID.
    """
    sched = get_scheduler()
    try:
        sched.remove_job(job_id)
        return True
    except Exception as e:
        print(f"Error removing job {job_id}: {e}")
        return False
