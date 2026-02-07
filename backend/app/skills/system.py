import base64
import io
import json
import mimetypes
from pathlib import Path

from app.core.filesystem import SessionWorkspace
from app.core.runtime_context import emit_event, get_session_id


def list_files(directory: str = "/") -> str:
    try:
        ws = SessionWorkspace(get_session_id())
        return json.dumps({"directory": directory, "files": ws.list_files(directory)}, ensure_ascii=False)
    except Exception as e:
        return f"Error listing files: {str(e)}"


def read_file(filepath: str, max_bytes: int = 1_000_000) -> str:
    try:
        ws = SessionWorkspace(get_session_id())
        filename = Path(str(filepath)).name
        mime_type, _ = mimetypes.guess_type(filename)

        if (mime_type == "application/pdf") or str(filepath).lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except Exception as e:
                return f"Error reading PDF: missing dependency pypdf ({str(e)})"
            raw = ws.read_bytes(filepath)
            if len(raw) > max_bytes:
                return json.dumps(
                    {"path": filepath, "mime_type": mime_type or "application/pdf", "size_bytes": len(raw), "truncated": True},
                    ensure_ascii=False,
                )
            reader = PdfReader(io.BytesIO(raw))
            parts: list[str] = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    parts.append("")
            return "\n".join(parts).strip()

        raw = ws.read_bytes(filepath)
        if len(raw) > max_bytes:
            return json.dumps(
                {"path": filepath, "mime_type": mime_type, "size_bytes": len(raw), "truncated": True},
                ensure_ascii=False,
            )

        is_text_like = bool(mime_type) and (
            mime_type.startswith("text/") or mime_type in ("application/json", "application/xml")
        )
        is_probably_binary = b"\x00" in raw
        if (mime_type and not is_text_like) or is_probably_binary:
            return json.dumps(
                {
                    "path": filepath,
                    "mime_type": mime_type,
                    "size_bytes": len(raw),
                    "base64": base64.b64encode(raw).decode("utf-8"),
                },
                ensure_ascii=False,
            )

        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {str(e)}"


def create_file(filepath: str, content: str, encoding: str = "utf-8") -> str:
    try:
        session_id = get_session_id()
        ws = SessionWorkspace(session_id)
        if encoding == "base64":
            meta = ws.write_base64(filepath, content)
        else:
            meta = ws.write_text(filepath, content, encoding=encoding)
        emit_event("artifact", {"session_id": session_id, "op": "write", "path": meta.get("path"), "meta": meta})
        return json.dumps({"saved": meta}, ensure_ascii=False)
    except Exception as e:
        return f"Error creating file: {str(e)}"


def update_file(filepath: str, start_line: int, end_line: int, new_content: str) -> str:
    try:
        session_id = get_session_id()
        ws = SessionWorkspace(session_id)
        original = ws.read_text(filepath)
        lines = original.splitlines(keepends=True)

        if start_line < 1:
            return "Error updating file: start_line must be >= 1"
        if end_line < 0:
            return "Error updating file: end_line must be >= 0"

        start_idx = start_line - 1
        if start_idx > len(lines):
            return "Error updating file: start_line out of range"

        if end_line == 0 or end_line < start_line:
            end_idx = start_idx
        else:
            if end_line > len(lines):
                return "Error updating file: end_line out of range"
            end_idx = end_line

        new_chunk = new_content
        updated_lines = lines[:start_idx] + [new_chunk] + lines[end_idx:]
        updated = "".join(updated_lines)
        meta = ws.write_text(filepath, updated)
        emit_event("artifact", {"session_id": session_id, "op": "update", "path": meta.get("path"), "meta": meta})
        return json.dumps({"saved": meta}, ensure_ascii=False)
    except Exception as e:
        return f"Error updating file: {str(e)}"


tools = [list_files, read_file, create_file, update_file]
