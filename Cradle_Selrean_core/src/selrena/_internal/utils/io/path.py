# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""Utility functions for paths used by selrena components."""

from pathlib import Path
from typing import Union


class ProjectPath:
    """Simple container of project-related directory constants."""

    CONFIGS_DIR: Path = Path("./config")
    ASSETS_DIR: Path = Path("./assets")
    DATA_DIR: Path = Path("./data")
    MODELS_DIR: Path = Path("./models")
    _proj = Path.cwd()
    # if we are running inside the package directory, move up one level
    if _proj.name.lower() == "cradle-selrena":
        _proj = _proj.parent
    PROJECT_ROOT: Path = _proj

    @classmethod
    def ensure_dirs(cls):
        for attr in ("CONFIGS_DIR", "ASSETS_DIR", "DATA_DIR", "MODELS_DIR"):
            d = getattr(cls, attr)
            d.mkdir(parents=True, exist_ok=True)


def normalize_path(p: Union[str, Path]) -> str:
    return str(Path(p))


def get_log_path(filename: str) -> Path:
    return Path("./logs") / filename


def get_config_path(*parts: str) -> Path:
    return Path("./config").joinpath(*parts)


def get_asset_path(*parts: str) -> Path:
    return Path("./assets").joinpath(*parts)


def get_data_path(*parts: str) -> Path:
    return Path("./data").joinpath(*parts)


def get_model_path(*parts: str) -> Path:
    return Path("./models").joinpath(*parts)


def get_relative_path(p: Union[str, Path]) -> str:
    # return path relative to current working directory
    try:
        return str(Path(p).relative_to(Path.cwd()))
    except Exception:
        return str(p)
