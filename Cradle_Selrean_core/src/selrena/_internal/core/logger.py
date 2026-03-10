# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""核心日志模块。

该组件集中管理全局日志配置和相关辅助工具，属于核心基础设施。
原实现位于 `utils/logger.py`，已迁移至内部位置，
utils 包仍提供简单的转发以保持兼容。
"""

import sys


from loguru import logger as _logger

# 为避免子模块导入本文件时出现循环依赖，
# 日志路径相关函数放在 io 子包中。

from selrena._internal.utils.io.path import get_log_path, normalize_path

# 日志配置参数（与旧版本行为一致）

LOG_FILE_NAME = "Selrean.log"

LOG_ROTATION = "10 MB"

LOG_RETENTION = "1 week"

LOG_COMPRESSION = "zip"


def _get_log_path() -> str:

    # 委托路径计算给 helper，确保文件目录存在

    path_obj = get_log_path(LOG_FILE_NAME)

    return normalize_path(path_obj)


def setup_logger():

    _logger.remove()

    log_path = _get_log_path()

    _logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    _logger.add(
        log_path,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        level="DEBUG",
        encoding="utf-8",
    )

    return _logger


# 模块初始化：创建 logger 实例

logger = setup_logger()


def get_logger(name: str):

    return logger.bind(name=name)


__all__ = ["logger", "get_logger"]
