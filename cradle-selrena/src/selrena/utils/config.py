from pathlib import Path
from typing import Any, Dict



def load_yaml(path: Path) -> Dict[str, Any]:
    from .logger import logger
    try:
        from cradle_selrena.utils.yaml_io import load_yaml as _load
        return _load(path)
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")
        return {}
