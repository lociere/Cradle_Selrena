import sys
import os
import platform
from typing import List, Any

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
IS_CONTAINER = os.path.exists('/.dockerenv') or os.path.exists('/run/secrets/kubernetes.io')

# -----------------------------------------------------------------------------
# 4. 获取器工具 (Typed Getters)
# -----------------------------------------------------------------------------

def get_bool(key: str, default: bool = False) -> bool:
    """安全的从环境变量获取布尔值 (支持 yes/true/1 等变体)"""
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on", "enable")

def get_int(key: str, default: int = 0) -> int:
    """安全的从环境变量获取整数"""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def get_list(key: str, separator: str = ",", default: List[str] = None) -> List[str]:
    """将环境变量按分隔符切分为列表"""
    val = os.getenv(key)
    if val is None:
        return default or []
    # 过滤空字符串并去除首尾空格
    return [item.strip() for item in val.split(separator) if item.strip()]

# -----------------------------------------------------------------------------
# 5. 兼容性接口 (Legacy Support)
# -----------------------------------------------------------------------------

def is_development() -> bool:
    return IS_DEVELOPMENT

def is_production() -> bool:
    return IS_PRODUCTION
