import sys
from pathlib import Path
from typing import Union, Optional
from cradle.utils.env import IS_PRODUCTION

# -------------------------- 核心路径初始化 --------------------------
def _get_project_root() -> Path:
    """
    智能获取项目根目录。
    优先级：
    1. 生产环境 (Frozen/EnvVar) -> sys.executable 所在目录
    2. 开发环境 -> 基于锚点文件 (pyproject.toml/README.md) 向上递归查找
    3. 兜底策略 -> 基于文件层级回退
    """
    # 1. 生产环境检测 (集成 env 模块的判断逻辑)
    if IS_PRODUCTION:
        # 在打包环境中，sys.executable 是 exe 文件路径
        # 根目录应该是 exe 所在的文件夹
        return Path(sys.executable).parent.resolve()

    # 2. 开发环境：基于锚点文件查找 (更稳健，不怕文件移动或结构调整)
    current_path = Path(__file__).resolve()
    # 从当前文件所在目录开始，向上遍历所有父级目录
    search_paths = [current_path] + list(current_path.parents)
    
    for path in search_paths:
        if path.is_file(): continue
        
        # 只要找到任意一个标志性项目文件，就锁定为根目录
        # 增加 .git 目录检测，这是最准确的项目根目录特征
        if (path / "pyproject.toml").exists() or \
           (path / "README.md").exists() or \
           (path / ".env").exists() or \
           (path / ".git").exists():
            return path
    
    # 3. 兜底：基于标准目录结构硬编码回退 (src/cradle/utils/path.py -> Root)
    # parents[0]=utils, parents[1]=cradle, parents[2]=src, parents[3]=ROOT
    try:
        # 如果 path.py 在 src/cradle/utils/ 下，向上 4 层就是根目录
        fallback = current_path.parents[3]
        if fallback.exists():
            return fallback
    except IndexError:
        pass
        
    # 4. 终极兜底：返回当前工作目录 (CWD)
    # 这通常是在 IPython 或特殊脚本执行环境下
    return Path.cwd()
        
# 1.初始化全局根目录
_PROJECT_ROOT = _get_project_root()

# 2. 定义所有核心目录的绝对路径（统一用Path对象，跨平台兼容）
class ProjectPath:
    # 顶层核心目录
    PROJECT_ROOT: Path = _PROJECT_ROOT
    CONFIGS_DIR: Path = PROJECT_ROOT / "configs"
    ASSETS_DIR: Path = PROJECT_ROOT / "assets"
    DATA_DIR: Path = PROJECT_ROOT / "data"
    
    # 运行时数据子目录
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    SCRIPTS_DIR: Path = PROJECT_ROOT / "scripts"
    DOCS_DIR: Path = PROJECT_ROOT / "docs"
    TESTS_DIR: Path = PROJECT_ROOT / "tests"
    
    # Assets 子目录
    ASSETS_IMAGES: Path = ASSETS_DIR / "images"
    ASSETS_SOUNDS: Path = ASSETS_DIR / "sounds"
    ASSETS_MODELS: Path = ASSETS_DIR / "models"
    
    # Data 子目录（自动创建）
    # 结构优化：分离系统数据(Runtime)与个体数据(Data)
    
    # 1. 系统运行时数据 (Runtime Data) -> 存放在 runtime/ 目录 (一次性、可随时清理)
    RUNTIME_DIR: Path = PROJECT_ROOT / "runtime"
    DATA_CACHE: Path = RUNTIME_DIR / "cache"  # 缓存 (pip, hub, tmp)
    DATA_TEMP: Path = RUNTIME_DIR / "temp"    # 运行时临时文件
    
    # 2. 个体价值数据 (Entity Data) -> 存放在 data/ 目录 (需持久化、备份)
    DATA_SELRENA: Path = DATA_DIR / "selrena" # 默认个体直接置于 data 根下或子目录
    
    # 映射具体业务路径
    DATA_MEMORY: Path = DATA_SELRENA / "memory"
    
    # Configs 核心文件路径
    SOUL_CONFIG: Path = CONFIGS_DIR / "soul.yaml"   # 灵魂配置 (包含 Persona 与 LLM)
    ENV_EXAMPLE: Path = PROJECT_ROOT / ".env.example"

    @classmethod
    def ensure_dirs(cls):
        """初始化项目时，自动创建所有必要的目录"""
        dirs_to_create = [
            cls.CONFIGS_DIR,
            cls.ASSETS_IMAGES,
            cls.ASSETS_SOUNDS,
            cls.ASSETS_MODELS,
            cls.RUNTIME_DIR,
            cls.DATA_CACHE,
            cls.DATA_TEMP,
            cls.DATA_DIR,
            cls.DATA_SELRENA,
            cls.DATA_MEMORY,
            cls.LOGS_DIR,
        ]
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)


# -------------------------- 便捷工具函数 --------------------------

def get_config_path(filename: str) -> Path:
    return ProjectPath.CONFIGS_DIR / filename

def get_asset_path(sub_dir: str, filename: str) -> Path:
    return ProjectPath.ASSETS_DIR / sub_dir / filename

def get_data_path(sub_dir: str, filename: Optional[str] = None) -> Path:
    base_path = ProjectPath.DATA_DIR / sub_dir
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / filename if filename else base_path

def get_log_path(filename: str = "app.log") -> Path:
    ProjectPath.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return ProjectPath.LOGS_DIR / filename

def get_model_path(model_name: str) -> Path:
    return ProjectPath.ASSETS_MODELS / model_name

def get_relative_path(path: Union[str, Path]) -> str:
    """获取相对于项目根目录的路径字符串（用于清洁日志显示）"""
    try:
        p = Path(path).resolve()
        # 处理 path 可能不在 project_root 下的情况（如 site-packages）
        if p.is_relative_to(ProjectPath.PROJECT_ROOT):
            return str(p.relative_to(ProjectPath.PROJECT_ROOT).as_posix())
        return str(p.as_posix())
    except (ValueError, AttributeError):
        return normalize_path(path)

def normalize_path(path: Union[str,Path]) -> str:
    return str(Path(path).resolve().as_posix())
  
__all__ = [
    "ProjectPath",
    "get_config_path",
    "get_asset_path",
    "get_data_path",
    "get_log_path",
    "get_model_path",
    "get_relative_path",
    "normalize_path"
]
  
# -------------------------- 初始化执行 --------------------------
ProjectPath.ensure_dirs()
