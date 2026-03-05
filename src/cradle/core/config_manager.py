import copy
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from cradle.core.env_config import env_settings
from cradle.schemas.configs.soul import LLMConfig, PersonaConfig, SoulConfig
from cradle.schemas.configs.system import AppConfig, SystemSettings
from cradle.utils.dicts import fill_defaults, merge_dicts, set_by_path
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.utils.yaml_io import read_yaml, write_yaml


class ConfigManager:
    """
    统一配置管理中心 (Single Source of Truth)
    
    结构优化：
    分离系统基础配置 (SystemSettings) 与核心生命配置 (SoulConfig)。

    1. SystemSettings: 对应 configs/settings.yaml + configs/vessel/*.yaml (基础设施、驱动、APP行为)
    2. SoulConfig:     对应 configs/soul/*.yaml (身份、记忆、认知模型)
    """

    # --- Constants & Mappings ---

    SYSTEM_ROOT_FILE = "settings.yaml"
    SOUL_ROOT_FILE = "llm.yaml"

    SYSTEM_MODULE_FILES: Dict[str, str] = {
        "perception": "perception.yaml",
        "presentation": "presentation.yaml",
        "model_manager": "model_manager.yaml",
        "napcat": "napcat.yaml",
    }

    SOUL_MODULE_FILES: Dict[str, str] = {
        "persona": "persona.yaml",
        "memory": "memory.yaml",
    }

    # 环境变量映射：使用 src.cradle.core.env_config.EnvSettings 作为唯一来源
    SYSTEM_ENV_MAPPINGS: tuple[tuple[str, str], ...] = (
        ("SELRENA_APP_DEBUG", "app.debug"),
        ("SELRENA_LOG_LEVEL", "app.log_level"),
        ("SELRENA_NAPCAT_ENABLE", "napcat.enable"),
        ("SELRENA_NAPCAT_ACCOUNT", "napcat.account"),
        ("SELRENA_NAPCAT_TOKEN", "napcat.token"),
        ("SELRENA_PERCEPTION_STRICT_WAKE_WORD", "perception.strict_wake_word"),
        ("SELRENA_PERCEPTION_VISION_ENABLED", "perception.vision.enabled"),
    )

    SOUL_ENV_MAPPINGS: tuple[tuple[str, str], ...] = (
        ("SELRENA_SOUL_STRATEGY_API_PROVIDER", "strategy.api_provider"),
        ("SELRENA_SOUL_STRATEGY_FALLBACK_TO_LOCAL", "strategy.fallback_to_local"),
    )

    SOUL_PREFIXES = ("persona.", "providers.", "strategy.", "memory.")
    SOUL_EXACT_KEYS = {"mock_response"}

    # --- Initialization ---

    def __init__(self):
        self.config_dir = ProjectPath.CONFIGS_DIR
        self._observers: List[Callable[[], None]] = []

        # 内存中的原始配置字典
        self.raw_sys: Dict[str, Any] = {}
        self.raw_soul: Dict[str, Any] = {}

        # 初始化为空对象
        self.sys_config: SystemSettings = SystemSettings()
        self.soul_config: SoulConfig = SoulConfig()

        # 执行初次加载
        try:
            self._load_and_build()
            logger.debug(
                f"配置管理器初始化完成. 环境: {self.app.app_name} v{self.app.version}")
        except Exception as e:
            logger.critical(f"系统配置加载失败: {e}")
            raise

    # --- Properties ---

    @property
    def app(self) -> AppConfig:
        return self.sys_config.app

    @property
    def llm(self) -> LLMConfig:
        return self.soul_config.llm

    @property
    def persona(self) -> PersonaConfig:
        return self.soul_config.persona

    # --- Public API ---

    def get_system(self) -> SystemSettings:
        return self.sys_config

    def get_soul(self) -> SoulConfig:
        return self.soul_config

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项值。支持点分路径访问 (e.g. 'napcat.token')
        自动识别是属于 system 配置还是 soul 配置。
        """
        target_path = self._normalize_key_path(key_path)
        
        # 1. 确定配置根对象
        if self._is_soul_key(target_path):
            current = self.soul_config
        else:
            current = self.sys_config
            
        # 2. 逐层遍历
        try:
            parts = target_path.split('.')
            for part in parts:
                # 优先尝试属性访问 (Pydantic Model)
                if hasattr(current, part):
                    current = getattr(current, part)
                # 其次尝试字典访问
                elif isinstance(current, dict) and part in current:
                    current = current[part]
                # 找不到则返回默认值
                else:
                    return default
            return current
        except Exception:
            return default

    def add_observer(self, callback: Callable[[], None]):
        """
        注册配置变更监听器。
        当配置通过 update 或 reload 发生变化时，会调用此回调函数。
        """
        self._observers.append(callback)

    def update(self, key_path: str, value: Any, save_to_disk: bool = True):
        """
        更新配置。智能判断属于 system 还是 soul。
        """
        target_path = self._normalize_key_path(key_path)
        is_soul_config = self._is_soul_key(target_path)

        # 1. 预校验
        try:
            if is_soul_config:
                test_raw = copy.deepcopy(self.raw_soul)
                set_by_path(test_raw, target_path, value)
                SoulConfig(**test_raw)
            else:
                test_raw = copy.deepcopy(self.raw_sys)
                set_by_path(test_raw, target_path, value)
                SystemSettings(**test_raw)
        except Exception as e:
            logger.error(f"无效的配置值 '{value}' (Key: {key_path}): {e}")
            raise ValueError(f"Invalid configuration: {e}")

        # 2. 持久化
        if save_to_disk:
            try:
                self._save_to_source_file(key_path, value)
                logger.info(f"配置已持久化: {key_path} = {value}")
            except Exception as e:
                logger.error(f"配置写入磁盘失败: {e}")
                raise e

        # 3. 热重载
        self.reload()

    def reload(self):
        """
        完全重载配置。
        从磁盘重新读取所有配置文件，重新应用环境变量，并重建配置对象。
        """
        try:
            self._load_and_build()
            self._notify_observers()
            logger.debug("配置系统已热重载")
        except Exception as e:
            logger.error(f"热重载失败: {e}")

    # --- Internal Logic: Load & Build ---

    def _load_and_build(self):
        # 1. System Config
        sys_raw = self._build_system_raw()

        # 2. Soul Config
        soul_raw = self._build_soul_raw()

        # 3. Env Overrides
        self._apply_env_settings(sys_raw, self.SYSTEM_ENV_MAPPINGS)
        self._apply_env_settings(soul_raw, self.SOUL_ENV_MAPPINGS)
        self._apply_api_keys_from_env(soul_raw)

        # 4. Build Objects
        new_sys_obj = SystemSettings(**sys_raw)
        new_soul_obj = SoulConfig(**soul_raw)

        # 5. Commit
        self.raw_sys = sys_raw
        self.raw_soul = soul_raw
        self.sys_config = new_sys_obj
        self.soul_config = new_soul_obj

        # 6. Auto Sync Defaults
        self._sync_missing_keys_to_disk()

    def _build_system_raw(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        self._merge_yaml(data, self.config_dir / self.SYSTEM_ROOT_FILE)

        for root_key, filename in self.SYSTEM_MODULE_FILES.items():
            self._merge_yaml(data, ProjectPath.VESSEL_DIR /
                             filename, root_key=root_key)

        # Secrets 覆盖 System
        self._merge_yaml(data, self.config_dir / "secrets.yaml")
        return data

    def _build_soul_raw(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        for root_key, filename in self.SOUL_MODULE_FILES.items():
            self._merge_yaml(data, ProjectPath.SOUL_DIR /
                             filename, root_key=root_key)

        self._merge_yaml(data, ProjectPath.SOUL_DIR / self.SOUL_ROOT_FILE)

        # Secrets 覆盖 Soul
        self._merge_yaml(data, self.config_dir / "secrets.yaml")
        return data

    # --- Internal Logic: Persistence & Sync ---

    def _save_to_source_file(self, key_path: str, value: Any):
        """根据路径路由写入 settings.yaml 或 soul 下对应的配置文件"""
        inner_key = self._normalize_key_path(key_path)
        target_file, relative_key = self._resolve_persist_target(inner_key)

        # 读取 -> 修改 -> 写入
        data = read_yaml(target_file)
        set_by_path(data, relative_key, value)
        write_yaml(target_file, data)

    def _resolve_persist_target(self, key_path: str) -> Tuple[Path, str]:
        # 1. Check Soul Modules
        soul_module_prefixes = {
            "persona.": ProjectPath.SOUL_DIR / self.SOUL_MODULE_FILES["persona"],
            "memory.": ProjectPath.SOUL_DIR / self.SOUL_MODULE_FILES["memory"],
        }
        for prefix, target_file in soul_module_prefixes.items():
            if key_path.startswith(prefix):
                return target_file, key_path.replace(prefix, "", 1)

        # 2. Check Soul Root (Providers/Strategy)
        if key_path.startswith("providers.") or key_path.startswith("strategy.") or key_path in self.SOUL_EXACT_KEYS:
            return ProjectPath.SOUL_DIR / self.SOUL_ROOT_FILE, key_path

        # 3. Check System Modules
        for root_key, filename in self.SYSTEM_MODULE_FILES.items():
            prefix = f"{root_key}."
            if key_path.startswith(prefix):
                return ProjectPath.VESSEL_DIR / filename, key_path.replace(prefix, "", 1)

        # 4. Fallback to System Root
        return self.config_dir / self.SYSTEM_ROOT_FILE, key_path

    def _sync_missing_keys_to_disk(self):
        """同步 SystemSettings 缺失键到 settings.yaml 与 vessel 子配置文件"""
        try:
            schema_defaults = SystemSettings().model_dump(mode='json')

            # Root Settings
            vessel_keys = set(self.SYSTEM_MODULE_FILES.keys())
            settings_defaults = {
                key: val for key, val in schema_defaults.items() if key not in vessel_keys
            }
            self._sync_defaults_to_file(
                self.config_dir / self.SYSTEM_ROOT_FILE, settings_defaults)

            # Module Settings
            for root_key, filename in self.SYSTEM_MODULE_FILES.items():
                module_defaults = schema_defaults.get(root_key, {})
                self._sync_defaults_to_file(
                    ProjectPath.VESSEL_DIR / filename, module_defaults)

        except Exception as e:
            logger.warning(f"自动同步配置失败: {e}")

    def _sync_defaults_to_file(self, path: Path, defaults: dict):
        current_data = read_yaml(path)
        updated, final_data = fill_defaults(current_data, defaults)
        if updated:
            logger.info(f"检测到 {path.name} 缺少新配置项，正在回填...")
            write_yaml(path, final_data)

    # --- Internal Logic: Environment & Helpers ---

    def _apply_env_settings(self, data: dict, mappings: tuple[tuple[str, str], ...]):
        for env_attr, target_path in mappings:
            val = getattr(env_settings, env_attr, None)
            if val is not None:
                try:
                    set_by_path(data, target_path, val)
                except Exception as e:
                    logger.warning(
                        f"Failed to apply env setting {env_attr}: {e}")

    def _apply_api_keys_from_env(self, soul_raw: dict):
        providers = soul_raw.get("providers")
        if not isinstance(providers, dict):
            return

        key_mapping = {
            "openai": env_settings.OPENAI_API_KEY,
            "deepseek": env_settings.DEEPSEEK_API_KEY,
            "qwen": env_settings.QWEN_API_KEY or env_settings.QWEN_API_KEY, # Fixed typo in original code if any, keeping robust
        }

        for provider_name, api_key in key_mapping.items():
            if api_key and provider_name in providers:
                if isinstance(providers[provider_name], dict):
                    providers[provider_name]["api_key"] = api_key

    def _merge_yaml(self, target: dict, path: Path, root_key: str = None):
        if not path.exists():
            return
        try:
            data = read_yaml(path)
            if root_key:
                target_sub = target.setdefault(root_key, {})
                merge_dicts(target_sub, data)
            else:
                merge_dicts(target, data)
        except Exception as e:
            logger.warning(f"读取配置 {path.name} 失败: {e}")

    def _normalize_key_path(self, key_path: str) -> str:
        return key_path.replace("soul.", "", 1) if key_path.startswith("soul.") else key_path

    def _is_soul_key(self, key_path: str) -> bool:
        if key_path in self.SOUL_EXACT_KEYS:
            return True
        return key_path.startswith(self.SOUL_PREFIXES)

    def _notify_observers(self):
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Config observer callback failed: {e}")


# 全局单例实例
global_config = ConfigManager()
