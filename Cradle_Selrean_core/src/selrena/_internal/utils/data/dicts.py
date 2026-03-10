# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Tuple


def _normalize_path(path: str, separator: str = ".") -> list[str]:
    return [segment for segment in path.split(separator) if segment]


def set_by_path(
    data: MutableMapping[str, Any],
    path: str,
    value: Any,
    *,
    separator: str = ".",
):
    keys = _normalize_path(path, separator)
    if not keys:
        raise ValueError("path 不能为空")

    current: MutableMapping[str, Any] = data
    for key in keys[:-1]:
        existing = current.get(key)
        if not isinstance(existing, MutableMapping):
            existing = {}
            current[key] = existing
        current = existing
    current[keys[-1]] = value


def get_by_path(
    data: Mapping[str, Any],
    path: str,
    default: Any = None,
    *,
    separator: str = ".",
) -> Any:
    keys = _normalize_path(path, separator)
    if not keys:
        return default

    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def has_path(data: Mapping[str, Any], path: str, *, separator: str = ".") -> bool:
    sentinel = object()
    return get_by_path(data, path, sentinel, separator=separator) is not sentinel


def merge_dicts(source: MutableMapping[str, Any], incoming: Mapping[str, Any]):
    for key, value in incoming.items():
        if (
            isinstance(value, Mapping)
            and key in source
            and isinstance(source[key], MutableMapping)
        ):
            merge_dicts(source[key], value)
        else:
            source[key] = value


def fill_defaults(
    current: MutableMapping[str, Any],
    defaults: Mapping[str, Any],
) -> Tuple[bool, MutableMapping[str, Any]]:
    updated = False
    for key, default_val in defaults.items():
        if key not in current:
            current[key] = default_val
            updated = True
        elif isinstance(default_val, Mapping) and isinstance(
            current.get(key), MutableMapping
        ):
            sub_updated, _ = fill_defaults(current[key], default_val)
            if sub_updated:
                updated = True
    return updated, current
