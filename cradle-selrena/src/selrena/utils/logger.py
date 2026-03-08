import sys

from loguru import logger

from selrena.utils.path import ProjectPath, normalize_path

# ---------------????----------------
LOG_FILE_NAME = "Selrean.log"   # ?????
LOG_ROTATION = "10 MB"          # ?????????????????????
LOG_RETETION = "1 week"         # ??????
LOG_COMPRESSION = "zip"         # ??????


def _get_log_path() -> str:
    '''????????'''
    log_dir = ProjectPath.LOGS_DIR
    log_file_path = log_dir / LOG_FILE_NAME
    return normalize_path(log_file_path)


def setup_logger():
    """?? loguru ??"""
    # ??????
    logger.remove()
    # ??????
    log_path = _get_log_path()

    # 1. ?????? (???)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 2. ?????
    logger.add(
        log_path,
        rotation=LOG_ROTATION,
        retention=LOG_RETETION,
        compression=LOG_COMPRESSION,
        level="DEBUG",
        encoding="utf-8"
    )

    return logger


# ???
setup_logger()

# ?? logger ???????
__all__ = ["logger"]
