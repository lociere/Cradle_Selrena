# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
import os
import platform
import sys
from typing import Callable, List, Optional, TypeVar

"""
Cradle Selrena Environment Utility
??????????????????????
"""

# -----------------------------------------------------------------------------
# 1. ???? (Execution Mode)
# -----------------------------------------------------------------------------

# ???????? PyInstaller/Nuitka ??
IS_FROZEN = getattr(sys, "frozen", False)

# ??????????????? (SELRENA_ENV=production|development)
_ENV_VAR = os.getenv("SELRENA_ENV", "").lower()

# ????
IS_PRODUCTION = IS_FROZEN or (_ENV_VAR == "production")
IS_DEVELOPMENT = not IS_PRODUCTION

# ?????????????????????
# ?????? SELRENA_DEBUG ? DEBUG
IS_DEBUG = os.getenv("SELRENA_DEBUG", "false").lower() in (
    "true",
    "1",
    "yes",
) or os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# -----------------------------------------------------------------------------
# 2. ?????? (OS Detection)
# -----------------------------------------------------------------------------

_SYSTEM = platform.system().lower()

IS_WINDOWS = _SYSTEM == "windows"
IS_LINUX = _SYSTEM == "linux"
IS_MACOS = _SYSTEM == "darwin"

# -----------------------------------------------------------------------------
# 3. ?????? (Runtime Context)
# -----------------------------------------------------------------------------


def _is_debugger_attached() -> bool:
    """?????????? (? VS Code Debugger)"""
    gettrace = getattr(sys, "gettrace", None)
    return (gettrace() is not None) if gettrace else False


IS_DEBUGGER_ATTACHED = _is_debugger_attached()

# ??????? Docker ? K8s ???
IS_CONTAINER = os.path.exists("/.dockerenv") or os.path.exists(
    "/run/secrets/kubernetes.io"
)

T = TypeVar("T")


def _env_parse(key: str, parser: Callable[[str], T], default: T) -> T:
    """??????????????????????"""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return parser(val)
    except Exception:
        return default


# -----------------------------------------------------------------------------
# 4. ????? (Typed Getters)
# -----------------------------------------------------------------------------


def env_bool(key: str, default: bool = False) -> bool:
    """????????????? (?? yes/true/1 ???)"""
    return _env_parse(
        key,
        lambda raw: raw.strip().lower() in ("true", "1", "yes", "on", "enable"),
        default,
    )


def env_int(key: str, default: int = 0) -> int:
    """????????????"""
    return _env_parse(key, lambda raw: int(raw.strip()), default)


def env_float(key: str, default: float = 0.0) -> float:
    """?????????????"""
    return _env_parse(key, lambda raw: float(raw.strip()), default)


def env_str(key: str, default: str = "") -> str:
    """???????????????? strip?"""
    return _env_parse(key, lambda raw: raw.strip(), default)


def env_list(
    key: str, separator: str = ",", default: Optional[List[str]] = None
) -> List[str]:
    """??????????????"""
    fallback = default or []
    return _env_parse(
        key,
        lambda raw: [item.strip() for item in raw.split(separator) if item.strip()],
        fallback,
    )
