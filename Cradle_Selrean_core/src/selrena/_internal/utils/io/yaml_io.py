# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from pathlib import Path
from typing import Any, Mapping

import yaml

from selrena._internal.utils.data.dicts import merge_dicts


def _to_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def read_yaml(path: str | Path) -> dict[str, Any]:
    path = _to_path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_yaml(path: str | Path, data: Mapping[str, Any]):
    path = _to_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(dict(data), f, allow_unicode=True, sort_keys=False)


def upsert_yaml(path: str | Path, patch: Mapping[str, Any]):
    path = _to_path(path)
    current = read_yaml(path)
    merge_dicts(current, patch)
    write_yaml(path, current)
