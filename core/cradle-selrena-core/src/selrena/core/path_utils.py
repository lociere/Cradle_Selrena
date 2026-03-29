"""路径工具：统一解析仓库根目录与全局 data/logs 目录。"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_repo_root(start: Path | None = None) -> Path:
    """向上查找仓库根目录（优先 pnpm-workspace.yaml / .git）。"""
    cur = (start or Path(__file__).resolve()).resolve()
    if cur.is_file():
        cur = cur.parent

    while True:
        if (cur / "pnpm-workspace.yaml").exists() or (cur / ".git").exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return Path.cwd()
        cur = parent


def resolve_global_data_dir(data_dir: str | None = None) -> Path:
    """解析全局 data 目录。相对路径按仓库根目录解释。"""
    if data_dir:
        p = Path(data_dir)
        if p.is_absolute():
            return p
        return resolve_repo_root() / p
    return resolve_repo_root() / "data"


def resolve_global_log_dir(data_dir: str | None = None, log_dir: str | None = None) -> Path:
    """解析全局日志目录。默认 <repo>/data/logs。"""
    base_data = resolve_global_data_dir(data_dir)
    if log_dir:
        log_path = Path(log_dir)
        if log_path.is_absolute():
            return log_path
        return base_data / log_path
    return base_data / "logs"


def ensure_dir(path: Path) -> Path:
    """确保目录存在并返回该路径。"""
    os.makedirs(path, exist_ok=True)
    return path
