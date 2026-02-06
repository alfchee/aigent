from app.core import scheduler_service

def start_scheduler():
    scheduler_service.start_scheduler()

def schedule_task(prompt: str, execute_at: str, use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a task to be executed by the agent at a specific time.
    
    Args:
        prompt: The instruction for the agent to execute.
        execute_at: The time to execute the task (ISO format: YYYY-MM-DD HH:MM:SS)
        use_react_loop: Whether to use ReAct loop for autonomous execution (default: True)
        max_iterations: Maximum reasoning cycles for ReAct loop (default: 10)
    """
    return scheduler_service.schedule_task(prompt, execute_at, use_react_loop, max_iterations)

def schedule_interval_task(prompt: str, interval_seconds: int, use_react_loop: bool = True, max_iterations: int = 10):
    """
    Schedules a task to run periodically every X seconds.
    
    Args:
        prompt: The instruction for the agent to execute.
        interval_seconds: The interval in seconds between executions.
        use_react_loop: Whether to use ReAct loop for autonomous execution (default: True)
        max_iterations: Maximum reasoning cycles for ReAct loop (default: 10)
    """
    return scheduler_service.schedule_interval_task(prompt, interval_seconds, use_react_loop, max_iterations)

tools = [schedule_task, schedule_interval_task]
