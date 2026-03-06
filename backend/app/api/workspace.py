import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.filesystem import SessionWorkspace


router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@router.get("/{session_id}/files")
async def list_workspace_files(session_id: str, directory: str = "/"):
    try:
        ws = SessionWorkspace(session_id)
        files = ws.list_files(directory)
        return {"session_id": session_id, "directory": directory, "files": files}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/files/{filename:path}")
async def get_workspace_file(session_id: str, filename: str, download: bool = False):
    try:
        ws = SessionWorkspace(session_id)
        abs_path = ws.safe_path(filename)
        if not abs_path.exists() or not abs_path.is_file():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        media_type, _ = mimetypes.guess_type(str(abs_path))
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            filename=abs_path.name if download else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
