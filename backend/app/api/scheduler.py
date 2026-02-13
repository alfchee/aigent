from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core import scheduler_service


router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/jobs")
def list_jobs():
    return scheduler_service.list_jobs()


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    sched = scheduler_service.get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    sched.remove_job(job_id)
    return {"status": "success", "message": f"Job {job_id} removed."}


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: str):
    sched = scheduler_service.get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    sched.pause_job(job_id)
    return {"status": "success", "message": f"Job {job_id} paused."}


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str):
    sched = scheduler_service.get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    sched.resume_job(job_id)
    return {"status": "success", "message": f"Job {job_id} resumed."}


@router.get("/logs")
def list_logs(job_id: Optional[str] = None, limit: int = 200):
    return scheduler_service.list_logs(job_id=job_id, limit=limit)
