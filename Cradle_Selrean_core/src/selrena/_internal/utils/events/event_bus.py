# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import Callable, Dict, List, Any

"""In-process event bus utilities used by internal components."""

# Simple global event bus for intra-process communication.
_subscribers: Dict[str, List[Callable[[Any], None]]] = {}


def subscribe(event_name: str, callback: Callable[[Any], None]) -> Callable[[], None]:
    """Register a callback for a given event name.

    Returns a function that can be called to unsubscribe.
    """
    if event_name not in _subscribers:
        _subscribers[event_name] = []
    _subscribers[event_name].append(callback)

    def unsubscribe():
        _subscribers[event_name].remove(callback)

    return unsubscribe


def publish(event_name: str, payload: Any = None) -> None:
    """Publish an event to all subscribers."""
    for cb in list(_subscribers.get(event_name, [])):
        try:
            result = cb(payload)
            if hasattr(result, "__await__"):
                import asyncio

                asyncio.create_task(result)
        except Exception:
            pass
