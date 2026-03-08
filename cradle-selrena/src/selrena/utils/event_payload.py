from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Optional, TypeVar

T = TypeVar("T")


def _is_valid_value(
    value: Any,
    *,
    value_type: type[T] | tuple[type[Any], ...] | None,
    allow_zero: bool,
) -> bool:
    if value_type is not None and not isinstance(value, value_type):
        return False
    if not allow_zero and isinstance(value, int) and value == 0:
        return False
    return True


def deep_find_first(node: Any, predicate: Callable[[Any, Any], bool]) -> Optional[Any]:
    """
    在嵌套的 ``dict/list`` 结构中深度优先查找首个满足条件的值。

    ``predicate`` 参数签名为 ``(key, value) -> bool``，
    当 ``node`` 为列表元素时，``key`` 为 ``None``。
    """

    def _walk(value: Any) -> Optional[Any]:
        if isinstance(value, Mapping):
            for key, field_value in value.items():
                if predicate(key, field_value):
                    return field_value

            for nested in value.values():
                found = _walk(nested)
                if found is not None:
                    return found
            return None

        if isinstance(value, list):
            for item in value:
                if predicate(None, item):
                    return item
                found = _walk(item)
                if found is not None:
                    return found
        return None

    return _walk(node)


def deep_find_first_by_keys(
    node: Any,
    keys: Iterable[str],
    *,
    value_type: type[T] | tuple[type[Any], ...] | None = int,
    allow_zero: bool = False,
) -> Optional[T]:
    """
    通过键名集合在嵌套结构中查找首个值。

    - ``value_type`` 为 ``None`` 时不做类型约束。
    - ``allow_zero=False`` 时会过滤整数 0。
    """
    key_set = set(keys)

    def _predicate(key: Any, value: Any) -> bool:
        if key not in key_set:
            return False
        return _is_valid_value(value, value_type=value_type, allow_zero=allow_zero)

    found = deep_find_first(node, _predicate)
    return found  # type: ignore[return-value]


def extract_fields(
    payload: Any,
    *,
    field_keys: Mapping[str, Sequence[str]],
    value_type: type[T] | tuple[type[Any], ...] | None = int,
    allow_zero: bool = False,
) -> dict[str, Optional[T]]:
    """
    从任意嵌套 payload 中按“字段名 -> 候选键集合”批量提取值。

    示例：
    ``field_keys={"user": ("user_id", "qq"), "group": ("group_id",)}``
    """
    result: dict[str, Optional[T]] = {}
    for field_name, keys in field_keys.items():
        result[field_name] = deep_find_first_by_keys(
            payload,
            keys,
            value_type=value_type,
            allow_zero=allow_zero,
        )
    return result


def resolve_event_fields(
    event: Any,
    *,
    field_keys: Mapping[str, Sequence[str]],
    payload_attr: str = "payload",
    value_type: type[T] | tuple[type[Any], ...] | None = int,
    allow_zero: bool = False,
) -> dict[str, Optional[T]]:
    """
    解析事件字段：先从事件对象属性读取，再回退到 ``payload`` 深度提取。

    ``field_keys`` 的每个字段可配置多个候选键名（按顺序尝试）。
    """
    payload = getattr(event, payload_attr, None)
    result: dict[str, Optional[T]] = {}

    for field_name, keys in field_keys.items():
        resolved: Optional[T] = None

        for key in keys:
            raw_value = getattr(event, key, None)
            if _is_valid_value(raw_value, value_type=value_type, allow_zero=allow_zero):
                resolved = raw_value
                break

        if resolved is None and payload is not None:
            resolved = deep_find_first_by_keys(
                payload,
                keys,
                value_type=value_type,
                allow_zero=allow_zero,
            )

        result[field_name] = resolved

    return result
