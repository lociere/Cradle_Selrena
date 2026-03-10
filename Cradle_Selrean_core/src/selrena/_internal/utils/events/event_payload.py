# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
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

        å¨åµå¥ç ``dict/list`` ç»æä¸­æ·±åº¦ä¼å
    æ¥æ¾é¦ä¸ªæ»¡è¶³æ¡ä»¶çå¼ã?



        ``predicate`` åæ°ç­¾åä¸?``(key, value) -> bool``ï¼?

        å½?``node`` ä¸ºåè¡¨å
    ç´ æ¶ï¼``key`` ä¸?``None``ã?

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

    éè¿é®åéåå¨åµå¥ç»æä¸­æ¥æ¾é¦ä¸ªå¼ã?



    - ``value_type`` ä¸?``None`` æ¶ä¸åç±»åçº¦æã?

    - ``allow_zero=False`` æ¶ä¼è¿æ»¤æ´æ° 0ã?

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

    ä»ä»»æåµå¥?payload ä¸­æâå­æ®µå -> åéé®éåâæ¹éæåå¼ã?



    ç¤ºä¾ï¼?

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

        è§£æäºä»¶å­æ®µï¼å
    ä»äºä»¶å¯¹è±¡å±æ§è¯»åï¼ååéå?``payload`` æ·±åº¦æåã?



        ``field_keys`` çæ¯ä¸ªå­æ®µå¯é
    ç½®å¤ä¸ªåéé®åï¼æé¡ºåºå°è¯ï¼ã?

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
