import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.filesystem import SessionWorkspace


logger = logging.getLogger("navibot.code_exec")


_DENY_MODULES = {
    "asyncio",
    "ctypes",
    "httpx",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pickle",
    "pty",
    "resource",
    "shlex",
    "shutil",
    "signal",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "urllib",
}

_DENY_CALLS = {"eval", "exec", "compile", "__import__", "open_code"}

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bos\.system\s*\(", re.IGNORECASE),
    re.compile(r"\bos\.popen\s*\(", re.IGNORECASE),
    re.compile(r"\bsubprocess\.", re.IGNORECASE),
    re.compile(r"\bsocket\.", re.IGNORECASE),
    re.compile(r"\burllib\.", re.IGNORECASE),
    re.compile(r"\bhttpx\.", re.IGNORECASE),
    re.compile(r"\brequests\.", re.IGNORECASE),
    re.compile(r"rm\s+-rf", re.IGNORECASE),
]


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _truncate(value: str, limit: int = 200_000) -> str:
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _iter_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return []
    if base.is_file():
        return [base]
    return (p for p in base.rglob("*") if p.is_file())


def _snapshot_tree(base: Path) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for p in _iter_files(base):
        try:
            st = p.stat()
        except Exception:
            continue
        rel = str(p.relative_to(base)).replace("\\", "/")
        snapshot[rel] = {"size_bytes": int(st.st_size), "mtime": float(st.st_mtime)}
    return snapshot


def _diff_snapshots(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    for rel, meta in after.items():
        if rel not in before:
            changed.append(rel)
            continue
        b = before[rel]
        if b.get("size_bytes") != meta.get("size_bytes") or b.get("mtime") != meta.get("mtime"):
            changed.append(rel)
    changed.sort()
    return changed


def _safe_make_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, content: str) -> None:
    _safe_make_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, _json_dumps(payload) + "\n")


def _append_jsonl(path: Path, payload: Any) -> None:
    _safe_make_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _run_id() -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:12]}"


def _extract_import_roots(code: str) -> tuple[list[str], str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        msg = e.msg or "SyntaxError"
        line = (e.text or "").rstrip("\n")
        if e.lineno:
            loc = f"line {e.lineno}"
            if e.offset:
                loc = f"{loc}:{e.offset}"
            msg = f"{msg} ({loc})"
        if line:
            msg = f"{msg}\n{line}"
        return [], msg

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.name or "").split(".", 1)[0].strip()
                if name:
                    roots.add(name)
        elif isinstance(node, ast.ImportFrom):
            name = (node.module or "").split(".", 1)[0].strip()
            if name:
                roots.add(name)
    return sorted(roots), None


def _validate_code(code: str) -> dict[str, Any]:
    imports, syntax_error = _extract_import_roots(code)
    if syntax_error:
        return {"ok": False, "status": "syntax_error", "reasons": [syntax_error], "imports": []}

    reasons: list[str] = []

    lowered = code.lower()
    for pat in _DANGEROUS_PATTERNS:
        if pat.search(lowered):
            reasons.append(f"Patrón peligroso detectado: {pat.pattern}")

    blocked_imports = [m for m in imports if m in _DENY_MODULES]
    if blocked_imports:
        reasons.append(f"Imports no permitidos: {', '.join(sorted(blocked_imports))}")

    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                fn = node.func.id
                if fn in _DENY_CALLS:
                    reasons.append(f"Llamada no permitida: {fn}()")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    p = node.args[0].value.strip()
                    if p.startswith(("/", "~")) or ".." in p or p.startswith("\\"):
                        reasons.append(f"Ruta no permitida en open(): {p}")

    return {"ok": len(reasons) == 0, "status": "blocked" if reasons else "ok", "reasons": reasons, "imports": imports}


def _missing_dependencies(import_roots: list[str]) -> list[str]:
    import importlib.util

    missing: list[str] = []
    for name in import_roots:
        if name in _DENY_MODULES:
            continue
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except Exception:
            missing.append(name)
    missing = sorted(set(missing))
    return missing


def _preexec_limits(timeout_seconds: int):
    try:
        import resource
    except Exception:
        return None

    def _fn():
        cpu = max(1, int(timeout_seconds) + 1)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        mem_bytes = int(os.getenv("NAVIBOT_CODE_EXEC_MAX_MEM_BYTES", str(1_500 * 1024 * 1024)))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
        fsize_bytes = int(os.getenv("NAVIBOT_CODE_EXEC_MAX_FSIZE_BYTES", str(200 * 1024 * 1024)))
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        except Exception:
            pass

    return _fn


def _run_python_subprocess(
    script_path: Path,
    run_dir: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> tuple[str, str, int, float, str]:
    args = [sys.executable, "-I", "-B", str(script_path)]
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        args,
        cwd=str(run_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=_preexec_limits(timeout_seconds),
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        elapsed = time.perf_counter() - t0
        return stdout or "", stderr or "", int(proc.returncode or 0), elapsed, "ok" if proc.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except Exception:
            stdout, stderr = "", ""
        elapsed = time.perf_counter() - t0
        return stdout or "", stderr or "", -1, elapsed, "timeout"


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _parse_python_error(stderr: str) -> dict[str, Any]:
    text = (stderr or "").strip()
    if not text:
        return {"type": None, "message": None}

    lines = text.splitlines()
    err_line = None
    for line in reversed(lines):
        if line.strip():
            err_line = line.strip()
            break

    err_type = None
    err_msg = None
    if err_line and ":" in err_line:
        parts = err_line.split(":", 1)
        err_type = parts[0].strip() or None
        err_msg = parts[1].strip() or None

    file_line = None
    for line in reversed(lines):
        m = re.search(r'File "([^"]+)", line (\d+)', line)
        if m:
            file_line = {"file": m.group(1), "line": int(m.group(2))}
            break

    return {"type": err_type, "message": err_msg, "location": file_line, "raw": _truncate(text, 20_000)}


def _prepend_import(code: str, import_line: str) -> str:
    if not code:
        return import_line + "\n"
    lines = code.splitlines()
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    while insert_at < len(lines) and (lines[insert_at].strip().startswith("#") or lines[insert_at].strip() == ""):
        insert_at += 1
    if import_line in code:
        return code
    new_lines = lines[:insert_at] + [import_line] + lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if code.endswith("\n") else "")


def _heuristic_autofix(code: str, error: dict[str, Any]) -> tuple[str | None, str | None]:
    et = (error.get("type") or "").strip()
    msg = (error.get("message") or "").strip()
    if et == "NameError" and "name 'np' is not defined" in msg:
        return _prepend_import(code, "import numpy as np"), "heuristic_import_numpy"
    if et == "NameError" and "name 'pd' is not defined" in msg:
        return _prepend_import(code, "import pandas as pd"), "heuristic_import_pandas"
    if et == "NameError" and "name 'plt' is not defined" in msg:
        return _prepend_import(code, "import matplotlib.pyplot as plt"), "heuristic_import_matplotlib"
    return None, None


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _llm_autofix(code: str, error: dict[str, Any]) -> tuple[str | None, str | None]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None, "missing_google_api_key"

    try:
        from google import genai
    except Exception:
        return None, "missing_google_genai_sdk"

    model = os.getenv("NAVIBOT_CODE_EXEC_MODEL", "gemini-2.0-flash")
    prompt = "\n".join(
        [
            "Corrige el siguiente código Python para que se ejecute correctamente.",
            "Restricciones de seguridad (obligatorias):",
            "- No uses os, sys, subprocess, socket, urllib, httpx, requests, importlib, shutil, signal, threading, multiprocessing.",
            "- No uses eval/exec/compile/__import__.",
            "- No accedas a rutas absolutas (que empiecen por /, \\\\, ~) ni uses '..' en rutas literales.",
            "- Si hay visualizaciones, guarda archivos con plt.savefig(...) en el directorio de trabajo actual.",
            "Devuelve SOLO el código corregido, sin Markdown ni explicaciones.",
            "",
            "ERROR:",
            error.get("raw") or "",
            "",
            "CÓDIGO:",
            code or "",
        ]
    ).strip()

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=model, contents=prompt)
        fixed = _strip_code_fences(getattr(resp, "text", "") or "")
        if not fixed:
            return None, "llm_empty_response"
        return fixed, "llm"
    except Exception:
        return None, "llm_error"


def execute_python_code(
    session_id: str,
    code: str,
    timeout_seconds: int = 30,
    auto_correct: bool = True,
    max_attempts: int = 3,
) -> dict[str, Any]:
    workspace = SessionWorkspace(session_id)
    root = workspace.safe_path("code_exec")
    _safe_make_dir(root)

    run_id = _run_id()
    run_dir = workspace.safe_path(f"code_exec/{run_id}")
    _safe_make_dir(run_dir)

    script_path = run_dir / "main.py"
    runs_index = root / "runs.jsonl"
    result_path = run_dir / "result.json"
    attempts_path = run_dir / "attempts.jsonl"
    try:
        session_link = run_dir / "session"
        if not session_link.exists():
            session_link.symlink_to(workspace.root, target_is_directory=True)
    except Exception:
        pass

    max_attempts = max(1, min(int(max_attempts or 1), 3))
    timeout_seconds = int(timeout_seconds or 30)
    timeout_seconds = max(1, min(timeout_seconds, 300))

    validation = _validate_code(code or "")
    if not validation.get("ok"):
        payload = {
            "run_id": run_id,
            "session_id": session_id,
            "started_at": _utc_now_iso(),
            "status": validation.get("status") or "blocked",
            "stdout": "",
            "stderr": _truncate("\n".join(validation.get("reasons") or [])),
            "execution_time_seconds": 0.0,
            "created_files": [],
            "attempts": [
                {
                    "attempt": 1,
                    "status": validation.get("status") or "blocked",
                    "stdout": "",
                    "stderr": _truncate("\n".join(validation.get("reasons") or [])),
                    "execution_time_seconds": 0.0,
                }
            ],
            "validation": validation,
        }
        _write_json(result_path, payload)
        _append_jsonl(
            runs_index,
            {
                "run_id": run_id,
                "started_at": payload["started_at"],
                "status": payload["status"],
                "execution_time_seconds": 0.0,
                "created_files": [],
            },
        )
        logger.warning(
            "code_execution_blocked",
            extra={"event": "code_execution_blocked", "payload": {"session_id": session_id, "run_id": run_id, "reasons": validation.get("reasons")}},
        )
        return payload

    missing = _missing_dependencies(validation.get("imports") or [])
    if missing:
        payload = {
            "run_id": run_id,
            "session_id": session_id,
            "started_at": _utc_now_iso(),
            "status": "deps_missing",
            "stdout": "",
            "stderr": _truncate(f"Dependencias faltantes: {', '.join(missing)}"),
            "missing_dependencies": missing,
            "execution_time_seconds": 0.0,
            "created_files": [],
            "attempts": [
                {
                    "attempt": 1,
                    "status": "deps_missing",
                    "stdout": "",
                    "stderr": _truncate(f"Dependencias faltantes: {', '.join(missing)}"),
                    "execution_time_seconds": 0.0,
                }
            ],
            "validation": validation,
        }
        _write_json(result_path, payload)
        _append_jsonl(
            runs_index,
            {
                "run_id": run_id,
                "started_at": payload["started_at"],
                "status": payload["status"],
                "execution_time_seconds": 0.0,
                "created_files": [],
            },
        )
        return payload

    created_files: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    started_at = _utc_now_iso()
    status = "error"
    final_stdout = ""
    final_stderr = ""
    total_execution_time = 0.0

    current_code = code or ""

    for attempt_idx in range(1, max_attempts + 1):
        code_to_run = current_code

        _write_text(script_path, code_to_run)
        before = _snapshot_tree(run_dir)

        env = {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "NAVIBOT_SESSION_ID": session_id,
            "NAVIBOT_RUN_ID": run_id,
            "NAVIBOT_OUTPUT_DIR": str(run_dir),
        }
        env.update({k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL", "TZ"}})

        stdout, stderr, returncode, elapsed, status = _run_python_subprocess(
            script_path=script_path,
            run_dir=run_dir,
            env=env,
            timeout_seconds=timeout_seconds,
        )
        total_execution_time += elapsed

        after = _snapshot_tree(run_dir)
        changed = _diff_snapshots(before, after)

        parsed_error = _parse_python_error(stderr)

        attempt_record = {
            "attempt": attempt_idx,
            "status": status,
            "code_sha256": _sha256_text(code_to_run),
            "code_preview": _truncate(code_to_run, 50_000),
            "stdout": _truncate(stdout),
            "stderr": _truncate(stderr),
            "error": parsed_error,
            "execution_time_seconds": round(elapsed, 6),
        }

        final_stdout = stdout
        final_stderr = stderr

        if status == "ok":
            created_files = []
            for rel in changed:
                p = run_dir / rel
                try:
                    meta = workspace._stat_file(p)
                except Exception:
                    continue
                created_files.append(meta)
            attempts.append(attempt_record)
            _append_jsonl(attempts_path, attempt_record)
            break

        if not auto_correct or attempt_idx >= max_attempts or status == "timeout":
            attempts.append(attempt_record)
            _append_jsonl(attempts_path, attempt_record)
            break

        fixed, fixed_by = _heuristic_autofix(current_code, parsed_error)
        if fixed is None:
            fixed, fixed_by = _llm_autofix(current_code, parsed_error)

        if not fixed:
            attempts.append(attempt_record)
            _append_jsonl(attempts_path, attempt_record)
            break

        v2 = _validate_code(fixed)
        if not v2.get("ok"):
            attempts.append(attempt_record)
            _append_jsonl(attempts_path, attempt_record)
            break
        missing2 = _missing_dependencies(v2.get("imports") or [])
        if missing2:
            attempts.append(attempt_record)
            _append_jsonl(attempts_path, attempt_record)
            break

        attempt_record["autocorrect"] = {"applied": True, "method": fixed_by}
        attempts.append(attempt_record)
        _append_jsonl(attempts_path, attempt_record)
        current_code = fixed

    payload: dict[str, Any] = {
        "run_id": run_id,
        "session_id": session_id,
        "started_at": started_at,
        "status": status,
        "stdout": _truncate(final_stdout),
        "stderr": _truncate(final_stderr),
        "execution_time_seconds": round(total_execution_time, 6),
        "created_files": created_files,
        "attempts": attempts,
        "validation": validation,
    }

    _write_json(result_path, payload)
    _append_jsonl(
        runs_index,
        {
            "run_id": run_id,
            "started_at": started_at,
            "status": status,
            "execution_time_seconds": round(total_execution_time, 6),
            "created_files": [f.get("path") for f in created_files],
        },
    )
    return payload


def list_code_runs(session_id: str, limit: int = 50) -> dict[str, Any]:
    workspace = SessionWorkspace(session_id)
    root = workspace.safe_path("code_exec")
    runs_index = root / "runs.jsonl"
    limit = max(1, min(int(limit or 50), 200))

    items: list[dict[str, Any]] = []
    if runs_index.exists():
        try:
            lines = runs_index.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        items.append(obj)
                except Exception:
                    continue
                if len(items) >= limit:
                    break
        except Exception:
            items = []

    items.reverse()
    return {"session_id": session_id, "items": items}


def cleanup_code_exec(
    session_id: str,
    max_age_hours: int = 24,
    remove_all: bool = False,
) -> dict[str, Any]:
    workspace = SessionWorkspace(session_id)
    root = workspace.safe_path("code_exec")
    if not root.exists():
        return {"session_id": session_id, "removed_runs": 0, "removed_files": 0}

    max_age_hours = int(max_age_hours or 24)
    max_age_hours = max(1, min(max_age_hours, 24 * 30))
    cutoff = time.time() - (max_age_hours * 3600)

    removed_runs = 0
    removed_files = 0

    for p in root.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith("."):
            continue
        if p.name == "__pycache__":
            continue
        try:
            st = p.stat()
        except Exception:
            continue
        if remove_all or st.st_mtime < cutoff:
            try:
                for fp in p.rglob("*"):
                    if fp.is_file():
                        removed_files += 1
                for fp in sorted(p.rglob("*"), reverse=True):
                    try:
                        if fp.is_file():
                            fp.unlink(missing_ok=True)
                        elif fp.is_dir():
                            fp.rmdir()
                    except Exception:
                        continue
                p.rmdir()
                removed_runs += 1
            except Exception:
                continue

    if remove_all:
        try:
            (root / "runs.jsonl").unlink(missing_ok=True)
        except Exception:
            pass

    return {"session_id": session_id, "removed_runs": removed_runs, "removed_files": removed_files}
