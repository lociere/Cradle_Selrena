from typing import Any, Dict, Tuple


def set_by_path(data: Dict[str, Any], path: str, value: Any):
    keys = path.split('.')
    current = data
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value


def get_by_path(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    keys = path.split('.')
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def has_path(data: Dict[str, Any], path: str) -> bool:
    sentinel = object()
    return get_by_path(data, path, sentinel) is not sentinel


def merge_dicts(source: Dict[str, Any], incoming: Dict[str, Any]):
    for key, value in incoming.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            merge_dicts(source[key], value)
        else:
            source[key] = value


def fill_defaults(current: Dict[str, Any], defaults: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    updated = False
    for key, default_val in defaults.items():
        if key not in current:
            current[key] = default_val
            updated = True
        elif isinstance(default_val, dict) and isinstance(current.get(key), dict):
            sub_updated, _ = fill_defaults(current[key], default_val)
            if sub_updated:
                updated = True
    return updated, current
