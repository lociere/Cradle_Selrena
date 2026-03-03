import os
import platform
import sys
from typing import Callable, List, Optional, TypeVar

"""
Cradle Selrena Environment Utility
提供系统级、运行时级和配置级的环境检测工具。
"""

# -----------------------------------------------------------------------------
# 1. 运行模式 (Execution Mode)
# -----------------------------------------------------------------------------

# 物理状态：是否被 PyInstaller/Nuitka 打包
IS_FROZEN = getattr(sys, "frozen", False)

# 逻辑状态：通过环境变量强制覆盖 (SELRENA_ENV=production|development)
_ENV_VAR = os.getenv("SELRENA_ENV", "").lower()

# 最终判定
IS_PRODUCTION = IS_FROZEN or (_ENV_VAR == "production")
IS_DEVELOPMENT = not IS_PRODUCTION

# 调试模式：通常用于开启详细日志或开发者工具
# 检查环境变量 SELRENA_DEBUG 或 DEBUG
IS_DEBUG = (
    os.getenv("SELRENA_DEBUG", "false").lower() in ("true", "1", "yes") or
    os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
)

# -----------------------------------------------------------------------------
# 2. 操作系统检测 (OS Detection)
# -----------------------------------------------------------------------------

_SYSTEM = platform.system().lower()

IS_WINDOWS = _SYSTEM == "windows"
IS_LINUX = _SYSTEM == "linux"
IS_MACOS = _SYSTEM == "darwin"

# -----------------------------------------------------------------------------
# 3. 运行时上下文 (Runtime Context)
# -----------------------------------------------------------------------------


def _is_debugger_attached() -> bool:
    """检测是否有调试器挂载 (如 VS Code Debugger)"""
    gettrace = getattr(sys, 'gettrace', None)
    return (gettrace() is not None) if gettrace else False


IS_DEBUGGER_ATTACHED = _is_debugger_attached()

# 检测是否运行在 Docker 或 K8s 容器中
IS_CONTAINER = os.path.exists(
    '/.dockerenv') or os.path.exists('/run/secrets/kubernetes.io')

T = TypeVar("T")


def _env_parse(key: str, parser: Callable[[str], T], default: T) -> T:
    """通用环境变量解析器：失败或缺失时回退默认值。"""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return parser(val)
    except Exception:
        return default

# -----------------------------------------------------------------------------
# 4. 获取器工具 (Typed Getters)
# -----------------------------------------------------------------------------


def env_bool(key: str, default: bool = False) -> bool:
    """安全的从环境变量获取布尔值 (支持 yes/true/1 等变体)"""
    return _env_parse(
        key,
        lambda raw: raw.strip().lower() in ("true", "1", "yes", "on", "enable"),
        default,
    )


def env_int(key: str, default: int = 0) -> int:
    """安全的从环境变量获取整数"""
    return _env_parse(key, lambda raw: int(raw.strip()), default)


def env_float(key: str, default: float = 0.0) -> float:
    """安全的从环境变量获取浮点值"""
    return _env_parse(key, lambda raw: float(raw.strip()), default)


def env_str(key: str, default: str = "") -> str:
    """安全的从环境变量获取字符串（自动 strip）"""
    return _env_parse(key, lambda raw: raw.strip(), default)


def env_list(key: str, separator: str = ",", default: Optional[List[str]] = None) -> List[str]:
    """将环境变量按分隔符切分为列表"""
    fallback = default or []
    return _env_parse(
        key,
        lambda raw: [item.strip() for item in raw.split(separator) if item.strip()],
        fallback,
    )
