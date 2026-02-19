import json

from app.core import scheduler_service

def start_scheduler():
    scheduler_service.start_scheduler()

def schedule_task(prompt: str, execute_at: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a task to be executed by the agent at a specific time.
    
    Args:
        prompt: The instruction for the agent to execute.
        execute_at: The time to execute the task (ISO format: YYYY-MM-DD HH:MM:SS)
        session_id: Session/workspace id to run the task in (default: "default")
        use_react_loop: Whether to use ReAct loop for autonomous execution (default: True)
        max_iterations: Maximum reasoning cycles for ReAct loop (default: 10)
    """
    return scheduler_service.schedule_task(prompt, execute_at, session_id, use_react_loop, max_iterations)

def schedule_interval_task(prompt: str, interval_seconds: int, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a task to run periodically every X seconds.
    
    Args:
        prompt: The instruction for the agent to execute.
        interval_seconds: The interval in seconds between executions.
        session_id: Session/workspace id to run the task in (default: "default")
        use_react_loop: Whether to use ReAct loop for autonomous execution (default: True)
        max_iterations: Maximum reasoning cycles for ReAct loop (default: 10)
    """
    return scheduler_service.schedule_interval_task(prompt, interval_seconds, session_id, use_react_loop, max_iterations)

def schedule_cron_task(prompt: str, cron: str, session_id: str = "default", use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a task using cron expression.

    Args:
        prompt: The instruction for the agent to execute.
        cron: Standard cron expression (e.g. "*/5 * * * *").
        session_id: Session/workspace id to run the task in (default: "default")
        use_react_loop: Whether to use ReAct loop for autonomous execution (default: True)
        max_iterations: Maximum reasoning cycles for ReAct loop (default: 10)
    """
    return scheduler_service.schedule_cron_task(prompt, cron, session_id, use_react_loop, max_iterations)

def list_job_logs(job_id: str | None = None, limit: int = 200) -> str:
    """
    Lists the execution logs of scheduled tasks.
    
    Args:
        job_id: Optional ID to filter by specific job.
        limit: Maximum number of logs to return.
    """
    logs = scheduler_service.list_logs(job_id=job_id, limit=limit)
    return json.dumps({"job_id": job_id, "logs": logs}, ensure_ascii=False)


def get_last_job_result(job_id: str) -> str:
    """
    Gets the last execution result of a task.
    
    Args:
        job_id: The task ID.
    """
    logs = scheduler_service.list_logs(job_id=job_id, limit=1)
    last = logs[-1] if logs else None
    return json.dumps({"job_id": job_id, "last": last}, ensure_ascii=False)


def list_scheduled_jobs() -> str:
    """
    Lists the active scheduled tasks (jobs).
    Returns a list with ID, name, prompt, next execution, etc.
    """
    jobs = scheduler_service.list_jobs()
    return json.dumps(jobs, ensure_ascii=False)


def delete_scheduled_job(job_id: str) -> str:
    """
    Deletes a scheduled task by its ID.
    Returns a success or error message.
    
    Args:
        job_id: The ID of the task to delete.
    """
    success = scheduler_service.delete_job(job_id)
    if success:
        return f"Tarea {job_id} eliminada correctamente."
    else:
        return f"Error al eliminar la tarea {job_id} (posiblemente no existe)."


tools = [schedule_task, schedule_interval_task, schedule_cron_task, list_job_logs, get_last_job_result, list_scheduled_jobs, delete_scheduled_job]
