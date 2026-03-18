import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from app.core.paths import workspace_db_dir

logger = logging.getLogger("navibot.core.scheduler")

class SchedulerService:
    """
    Task Scheduler for Cron Jobs (e.g., recurring summaries, cleanup).
    Persists jobs to SQLite database.
    """
    def __init__(self, db_url: str | None = None):
        if db_url is None:
            db_path = workspace_db_dir() / "scheduler.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path.as_posix()}"
        jobstores = {
            'default': SQLAlchemyJobStore(url=db_url)
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores, 
            executors=executors, 
            job_defaults=job_defaults,
            timezone="UTC"
        )

    def start(self):
        try:
            self.scheduler.start()
            logger.info("Scheduler started.")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown.")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

    def add_job(self, func, trigger, **kwargs):
        """Add a new job to the scheduler."""
        try:
            job = self.scheduler.add_job(func, trigger, **kwargs)
            logger.info(f"Added job: {job.id}")
            return job.id
        except Exception as e:
            logger.error(f"Failed to add job: {e}")
            return None

    def get_jobs(self):
        return self.scheduler.get_jobs()

# Example usage:
# scheduler = SchedulerService()
# scheduler.add_job(my_func, 'interval', minutes=5)
