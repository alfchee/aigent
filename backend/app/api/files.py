import mimetypes
from pathlib import Path
from typing import Optional
 
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
 
from app.core.filesystem import SessionWorkspace
from app.core.runtime_context import emit_event
 
 
router = APIRouter()
 
 
@router.get("/api/files/{session_id}")
async def list_session_files(session_id: str, directory: str = "/"):
    ws = SessionWorkspace(session_id)
    return {"session_id": session_id, "files": ws.list_files(directory)}
 
 
@router.get("/api/files/{session_id}/{filepath:path}")
async def get_session_file(session_id: str, filepath: str, download: bool = False):
    ws = SessionWorkspace(session_id)
    try:
        target = ws._safe_path(filepath)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
 
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
 
    filename = Path(filepath).name
    media_type, _ = mimetypes.guess_type(filename)
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return FileResponse(path=target, media_type=media_type or "application/octet-stream", headers=headers)
 
 
@router.post("/api/upload")
async def upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    target_path: Optional[str] = Form(None),
):
    ws = SessionWorkspace(session_id)
    safe_name = Path(file.filename or "upload.bin").name
    rel = target_path.strip() if target_path else f"uploads/{safe_name}"
 
    try:
        content = await file.read()
        meta = ws.write_bytes(rel, content)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    emit_event("artifact", {"session_id": session_id, "op": "upload", "path": meta.get("path"), "meta": meta})
 
    return {"session_id": session_id, "saved": meta}
