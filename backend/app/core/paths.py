from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def workspace_root() -> Path:
    return repo_root() / "workspace"


def workspace_db_dir() -> Path:
    return workspace_root() / "db"


def workspace_config_dir() -> Path:
    return workspace_root() / "config"
