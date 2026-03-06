from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.code_execution_service import cleanup_code_exec, execute_python_code, list_code_runs


router = APIRouter()


class ExecuteCodeRequest(BaseModel):
    session_id: str = "default"
    code: str
    timeout_seconds: int = 30
    auto_correct: bool = True
    max_attempts: int = 3


@router.post("/api/execute-code")
def execute_code(request: ExecuteCodeRequest):
    try:
        cleanup_code_exec(request.session_id, max_age_hours=24, remove_all=False)
        return execute_python_code(
            session_id=request.session_id,
            code=request.code,
            timeout_seconds=request.timeout_seconds,
            auto_correct=request.auto_correct,
            max_attempts=request.max_attempts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/code-results/{session_id}")
def code_results(session_id: str, limit: int = 50):
    try:
        cleanup_code_exec(session_id, max_age_hours=24, remove_all=False)
        return list_code_runs(session_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/code-cleanup/{session_id}")
def code_cleanup(session_id: str):
    try:
        return cleanup_code_exec(session_id, remove_all=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

