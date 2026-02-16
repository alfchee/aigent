import json
from typing import Any

from app.core.code_execution_service import execute_python_code
from app.core.runtime_context import emit_event, get_session_id


def execute_python(
    code: str,
    timeout_seconds: int = 30,
    auto_correct: bool = True,
    max_attempts: int = 3,
) -> str:
    """
    Ejecuta código Python en un entorno seguro y aislado.
    
    Args:
        code: El código Python a ejecutar.
        timeout_seconds: Tiempo máximo de ejecución.
        auto_correct: Si es True, intenta corregir errores comunes.
        max_attempts: Número máximo de intentos de corrección.
        
    Returns:
        JSON string con el resultado de la ejecución (stdout, stderr, created_files).
    """
    try:
        session_id = get_session_id()
        result: dict[str, Any] = execute_python_code(
            session_id=session_id,
            code=code,
            timeout_seconds=timeout_seconds,
            auto_correct=auto_correct,
            max_attempts=max_attempts,
        )
        for meta in result.get("created_files") or []:
            path = meta.get("path")
            if path:
                emit_event("artifact", {"session_id": session_id, "op": "write", "path": path, "meta": meta})
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"Error executing python: {str(e)}"


tools = [execute_python]

