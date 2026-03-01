from pathlib import Path
from typing import Any, Dict

import yaml
from cradle.utils.dicts import merge_dicts


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_yaml(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def upsert_yaml(path: Path, patch: Dict[str, Any]):
    current = read_yaml(path)
    merge_dicts(current, patch)
    write_yaml(path, current)
