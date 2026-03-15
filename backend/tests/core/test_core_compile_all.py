import py_compile
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2] / "app" / "core"
CORE_FILES = sorted([p for p in CORE_DIR.rglob("*.py") if p.is_file()])


def test_core_directory_has_python_scripts():
    assert CORE_FILES


def test_compile_all_core_scripts():
    failures = []
    for file_path in CORE_FILES:
        try:
            py_compile.compile(str(file_path), doraise=True)
        except Exception as exc:
            failures.append(f"{file_path}: {exc}")
    assert not failures, "\n".join(failures)
