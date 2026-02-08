import json
from pathlib import Path

from app.core.filesystem import SessionWorkspace


def get_filesystem_tools(session_id: str):
    workspace = SessionWorkspace(session_id)

    def create_file(filename: str, content: str) -> str:
        try:
            meta = workspace.write_text(filename, content)
            return json.dumps({"saved": meta}, ensure_ascii=False)
        except Exception as e:
            return f"Error creating file: {str(e)}"

    def read_file(filename: str) -> str:
        try:
            return workspace.read_text(filename)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def list_files(directory: str = "/") -> str:
        try:
            files = workspace.list_files(directory)
            if not files:
                return "El workspace está vacío."
            return json.dumps({"directory": directory, "files": files}, ensure_ascii=False)
        except Exception as e:
            return f"Error listing files: {str(e)}"

    return [create_file, read_file, list_files]

