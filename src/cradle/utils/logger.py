import sys

from loguru import logger
from cradle.utils.path import (
    ProjectPath,
    normalize_path
)


# ---------------私有常量----------------
LOG_FILE_NAME = "Selrean.log"   # 日志文件名
LOG_ROTATION = "10 MB"          # 日志轮转大小，可通过配置管理器扩展为可配置
LOG_RETETION = "1 week"         # 日志保留时间
LOG_COMPRESSION = "zip"         # 日志压缩格式

def _get_log_path() -> str:
    '''生成日志文件路径'''
    log_dir = ProjectPath.LOGS_DIR
    log_file_path = log_dir / LOG_FILE_NAME
    return normalize_path(log_file_path)
        
def setup_logger():
    """配置 loguru 日志"""
    # 移除默认配置
    logger.remove()
    # 获取日志路径
    log_path = _get_log_path()

    # 1. 输出到控制台 (带颜色)
    logger.add(
        sys.stderr, 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 2. 输出到文件
    logger.add(
        log_path,
        rotation=LOG_ROTATION,
        retention=LOG_RETETION,
        compression=LOG_COMPRESSION,
        level="DEBUG",
        encoding="utf-8"
    )

    return logger

# 初始化
setup_logger()

# 导出 logger 实例供全局使用
__all__ = ["logger"]
