import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import os

# We will import NaviBot lazily or inside the function to avoid circular imports if possible,
# but since agent.py imports skills inside __init__, top level import might be safe.
# However, to be safe and clean, we'll import inside the execution function or use a factory.

scheduler = None

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
    timeout_seconds: int = 300
):
    """
    Execute an agent task with optional ReAct loop.
    
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
    from app.core.runtime_context import reset_event_callback, reset_session_id, set_event_callback, set_session_id
    
    try:
        session_token = set_session_id(session_id)
        callback_token = set_event_callback(None)
        # Instantiate a fresh agent for this task
        bot = NaviBot()
        
        if use_react_loop:
            # Use ReAct loop for autonomous multi-turn execution
            result = await bot.send_message_with_react(
                prompt,
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds
            )
            
            print(f"\n{'='*60}")
            print(f"Task Execution Complete")
            print(f"Iterations: {result['iterations']}")
            print(f"Termination: {result['termination_reason']}")
            print(f"Execution Time: {result['execution_time_seconds']}s")
            print(f"{'='*60}")
            print(f"Final Response: {result['response']}")
            print(f"{'='*60}\n")
            
            # Print reasoning trace for debugging
            if result.get('reasoning_trace'):
                print("\nReasoning Trace:")
                for trace_line in result['reasoning_trace']:
                    print(trace_line)
        else:
            # Simple single-turn execution (backward compatibility)
            response = await bot.send_message(prompt)
            print(f"\n{'='*60}")
            print(f"Task Execution Result: {response}")
            print(f"{'='*60}\n")
            
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"Error executing task: {e}")
        print(f"{'='*60}\n")
    finally:
        try:
            reset_session_id(session_token)
            reset_event_callback(callback_token)
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
    try:
        run_date = datetime.fromisoformat(execute_at)
        sched.add_job(
            execute_agent_task, 
            DateTrigger(run_date=run_date), 
            args=[prompt, session_id, use_react_loop, max_iterations]
        )
        mode = "ReAct loop" if use_react_loop else "simple"
        return f"Task '{prompt}' scheduled for {execute_at} ({mode} mode)"
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
    try:
        sched.add_job(
            execute_agent_task, 
            IntervalTrigger(seconds=interval_seconds), 
            args=[prompt, session_id, use_react_loop, max_iterations]
        )
        mode = "ReAct loop" if use_react_loop else "simple"
        return f"Task '{prompt}' scheduled every {interval_seconds} seconds ({mode} mode)"
    except Exception as e:
        return f"Error scheduling task: {str(e)}"
