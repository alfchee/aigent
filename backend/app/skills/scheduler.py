from app.core import scheduler_service

def start_scheduler():
    scheduler_service.start_scheduler()

def schedule_task(prompt: str, execute_at: str):
    """
    Schedules a task to be executed by the agent at a specific time.
    
    Args:
        prompt: The instruction for the agent to execute.
        execute_at: The time to execute the task (ISO format: YYYY-MM-DD HH:MM:SS)
    """
    return scheduler_service.schedule_task(prompt, execute_at)

def schedule_interval_task(prompt: str, interval_seconds: int):
    """
    Schedules a task to run periodically every X seconds.
    
    Args:
        prompt: The instruction for the agent to execute.
        interval_seconds: The interval in seconds between executions.
    """
    return scheduler_service.schedule_interval_task(prompt, interval_seconds)

tools = [schedule_task, schedule_interval_task]
