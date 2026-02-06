
import asyncio
import os
from datetime import datetime, timedelta
from app.core import scheduler_service

# Mock NaviBot to avoid real API calls during verification if strict logic not needed,
# OR we rely on the fact that GOOGLE_API_KEY might be missing and the agent assumes mock mode or fails gracefully.
# But for the test to pass, we need `execute_agent_task` to run without error.
# The current agent implementation tries to invoke Gemini.
# If we don't have an API key, it might fail. Only way to verify without key is mocking.

# However, the user said "Work with the Backend application".
# Let's assume we can run it. If it fails due to key, we'll see.
# But `execute_agent_task` uses `NaviBot`.

async def run_verification():
    print("Starting verification...")
    # 1. Start Scheduler
    scheduler_service.start_scheduler()
    
    # 2. Schedule a task for 5 seconds from now
    run_date = datetime.now() + timedelta(seconds=5)
    prompt = "Say hello from verify script"
    print(f"Scheduling task: '{prompt}' at {run_date}")
    
    scheduler_service.schedule_task(prompt, run_date.isoformat())
    
    # 3. Wait to see if it executes (monitoring stdout)
    print("Waiting for execution...")
    await asyncio.sleep(10)
    
    print("Verification finished.")

if __name__ == "__main__":
    asyncio.run(run_verification())
