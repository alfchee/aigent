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

async def execute_agent_task(prompt: str):
    """
    The job function executing the agent.
    """
    print(f"Executing scheduled task with prompt: {prompt}")
    from app.core.agent import NaviBot
    
    try:
        # Instantiate a fresh agent for this task
        # Review: In the future, we might want to pass context or use a specific user session
        bot = NaviBot() 
        response = await bot.send_message(prompt)
        print(f"Task Execution Result: {response}")
    except Exception as e:
        print(f"Error executing task: {e}")

def start_scheduler():
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        print("Scheduler started with persistent storage.")

def schedule_task(prompt: str, execute_at: str):
    """
    Schedules a one-off task.
    """
    sched = get_scheduler()
    try:
        run_date = datetime.fromisoformat(execute_at)
        sched.add_job(execute_agent_task, DateTrigger(run_date=run_date), args=[prompt])
        return f"Task '{prompt}' scheduled for {execute_at}"
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD HH:MM:SS"
    except Exception as e:
        return f"Error scheduling task: {str(e)}"

def schedule_interval_task(prompt: str, interval_seconds: int):
    """
    Schedules a recurring task.
    """
    sched = get_scheduler()
    try:
        sched.add_job(execute_agent_task, IntervalTrigger(seconds=interval_seconds), args=[prompt])
        return f"Task '{prompt}' scheduled every {interval_seconds} seconds"
    except Exception as e:
        return f"Error scheduling task: {str(e)}"
