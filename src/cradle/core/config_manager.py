import os
import copy
from pathlib import Path
from typing import Dict, Any, Callable, List, Tuple
from cradle.schemas import SystemSettings, SoulConfig, AppConfig, LLMConfig, PersonaConfig
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.utils.yaml_io import read_yaml, write_yaml
from cradle.utils.dicts import set_by_path, merge_dicts, fill_defaults
from cradle.core.env_config import env_settings

# ConfigManager 初始化时不再直接调用 load_dotenv，而是通过 env_settings 加载
# load_dotenv() - Removed

class ConfigManager:
    """
    统一配置管理中心 (Single Source of Truth)
    
    结构优化：
    分离系统基础配置 (SystemSettings) 与核心生命配置 (SoulConfig)。
    
    1. SystemSettings: 对应 configs/settings.yaml + configs/vessel/*.yaml (基础设施、驱动、APP行为)
    2. SoulConfig:     对应 configs/soul/*.yaml (身份、记忆、认知模型)
    """
    SYSTEM_ROOT_FILE = "settings.yaml"

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

    SOUL_ROOT_FILE = "llm.yaml"

    # 环境变量映射：使用 src.cradle.core.env_config.EnvSettings 作为唯一来源
    # 格式: (EnvSettings_Attribute, Config_Key_Path)
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
        ("SELRENA_SOUL_ACTIVE_PROVIDER", "active_provider"),
        ("SELRENA_SOUL_STRATEGY_ENABLED", "strategy.enabled"),
        ("SELRENA_SOUL_STRATEGY_API_PROVIDER", "strategy.api_provider"),
        ("SELRENA_SOUL_STRATEGY_FALLBACK_TO_LOCAL", "strategy.fallback_to_local"),
    )


    SOUL_PREFIXES = ("persona.", "providers.", "strategy.", "memory.")
    SOUL_EXACT_KEYS = {"active_provider", "mock_response"}

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
            logger.debug(f"配置管理器初始化完成. 环境: {self.app.app_name} v{self.app.version}")
        except Exception as e:
            logger.critical(f"系统配置加载失败: {e}")
            raise

    # 快捷引用 (Properties)
    @property
    def app(self) -> AppConfig:
        return self.sys_config.app

    @property
    def llm(self) -> LLMConfig:
        return self.soul_config.llm

    @property
    def persona(self) -> PersonaConfig:
        return self.soul_config.persona

    # -------------------------------------------------------------------------
    # 公共 API (Public API)
    # -------------------------------------------------------------------------
    
    def get_system(self) -> SystemSettings:
        return self.sys_config

    def get_soul(self) -> SoulConfig:
        return self.soul_config

    def add_observer(self, callback: Callable[[], None]):
        """
        注册配置变更监听器。
        当配置通过 update 或 reload 发生变化时，会调用此回调函数。
        适用于 UI 刷新或服务重启等场景。
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
        成功后会触发所有观察者的回调。
        """
        try:
            self._load_and_build()
            self._notify_observers()
            logger.debug("配置系统已热重载")
        except Exception as e:
            logger.error(f"热重载失败: {e}")
            # 注意：这里我们不回滚 self.root，保持最后一次已知的良好状态，避免系统崩溃

    # -------------------------------------------------------------------------
    # 内部逻辑：加载与构建 (Internal: Loading Logic)
    # -------------------------------------------------------------------------

    def _load_and_build(self):
        # --- 1. System Config ---
        sys_raw = self._build_system_raw()

        # --- 2. Soul Config ---
        soul_raw = self._build_soul_raw()

        # --- 3. Env Overrides (From EnvSettings) ---
        self._apply_env_settings(sys_raw, self.SYSTEM_ENV_MAPPINGS)
        self._apply_env_settings(soul_raw, self.SOUL_ENV_MAPPINGS)
        self._apply_api_keys_from_env(soul_raw)
        
        # --- 4. Build ---
        new_sys_obj = SystemSettings(**sys_raw)
        new_soul_obj = SoulConfig(**soul_raw)

        # --- 5. Commit ---
        self.raw_sys = sys_raw
        self.raw_soul = soul_raw
        self.sys_config = new_sys_obj
        self.soul_config = new_soul_obj
        
        # --- 6. Auto Sync System Settings ---
        self._sync_missing_keys_to_disk()

    def _build_system_raw(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        self._merge_yaml(data, self.config_dir / self.SYSTEM_ROOT_FILE)

        for root_key, filename in self.SYSTEM_MODULE_FILES.items():
            self._merge_yaml(data, ProjectPath.VESSEL_DIR / filename, root_key=root_key)

        # Secrets 也可以覆盖系统配置 (如数据库密码)
        self._merge_yaml(data, self.config_dir / "secrets.yaml")
        return data

    def _build_soul_raw(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        for root_key, filename in self.SOUL_MODULE_FILES.items():
            self._merge_yaml(data, ProjectPath.SOUL_DIR / filename, root_key=root_key)

        self._merge_yaml(data, ProjectPath.SOUL_DIR / self.SOUL_ROOT_FILE)

        # Secrets 覆盖 Soul (如 LLM API Key)
        self._merge_yaml(data, self.config_dir / "secrets.yaml")
        return data

    def _save_to_source_file(self, key_path: str, value: Any):
        """
        根据路径路由写入 settings.yaml 或 soul 下对应的配置文件
        """
        inner_key = self._normalize_key_path(key_path)
        target_file, relative_key = self._resolve_persist_target(inner_key)
            
        # 读取 -> 修改 -> 写入
        data = read_yaml(target_file)

        # 写入
        set_by_path(data, relative_key, value)
        write_yaml(target_file, data)

    def _notify_observers(self):
        """通知所有注册的观察者配置已变更"""
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Config observer callback failed: {e}")

    # -------------------------------------------------------------------------
    # 自动同步逻辑 (Auto Sync)
    # -------------------------------------------------------------------------

    def _sync_missing_keys_to_disk(self):
        """同步 SystemSettings 缺失键到 settings.yaml 与 vessel 子配置文件"""
        settings_path = self.config_dir / self.SYSTEM_ROOT_FILE
        try:
            schema_defaults = SystemSettings().model_dump(mode='json')

            vessel_keys = set(self.SYSTEM_MODULE_FILES.keys())
            settings_defaults = {
                key: val for key, val in schema_defaults.items() if key not in vessel_keys
            }

            self._sync_defaults_to_file(settings_path, settings_defaults)

            for root_key, filename in self.SYSTEM_MODULE_FILES.items():
                module_defaults = schema_defaults.get(root_key, {})
                self._sync_defaults_to_file(ProjectPath.VESSEL_DIR / filename, module_defaults)
        except Exception as e:
            logger.warning(f"自动同步配置失败: {e}")

    def _resolve_persist_target(self, key_path: str) -> Tuple[Path, str]:
        soul_module_prefixes = {
            "persona.": ProjectPath.SOUL_DIR / self.SOUL_MODULE_FILES["persona"],
            "memory.": ProjectPath.SOUL_DIR / self.SOUL_MODULE_FILES["memory"],
        }
        for prefix, target_file in soul_module_prefixes.items():
            if key_path.startswith(prefix):
                return target_file, key_path.replace(prefix, "", 1)

        if key_path.startswith("providers.") or key_path.startswith("strategy.") or key_path in self.SOUL_EXACT_KEYS:
            return ProjectPath.SOUL_DIR / self.SOUL_ROOT_FILE, key_path

        for root_key, filename in self.SYSTEM_MODULE_FILES.items():
            prefix = f"{root_key}."
            if key_path.startswith(prefix):
                return ProjectPath.VESSEL_DIR / filename, key_path.replace(prefix, "", 1)

        return self.config_dir / self.SYSTEM_ROOT_FILE, key_path

    def _sync_defaults_to_file(self, path: Path, defaults: dict):
        current_data = read_yaml(path)

        updated, final_data = fill_defaults(current_data, defaults)
        if not updated:
            return

        logger.info(f"检测到 {path.name} 缺少新配置项，正在回填...")
        write_yaml(path, final_data)

    # -------------------------------------------------------------------------
    # 辅助方法 (Helpers)
    # -------------------------------------------------------------------------

    def _merge_yaml(self, target: dict, path: Path, root_key: str = None):
        """读取并合并 YAML 文件到目标字典中"""
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
        """规范化配置路径，兼容 soul.xxx 的前缀写法。"""
        return key_path.replace("soul.", "", 1) if key_path.startswith("soul.") else key_path

    def _is_soul_key(self, key_path: str) -> bool:
        """判断 key_path 是否属于 Soul 配置树。"""
        if key_path in self.SOUL_EXACT_KEYS:
            return True
        return key_path.startswith(self.SOUL_PREFIXES)

    def _apply_env_settings(self, data: dict, mappings: tuple[tuple[str, str], ...]):
        """从 EnvSettings 对象应用环境变量覆盖"""
        for env_attr, target_path in mappings:
            # 获取 Pydantic 设置中的值
            val = getattr(env_settings, env_attr, None)
            if val is not None:
                try:
                    set_by_path(data, target_path, val)
                    # logger.trace(f"Env override: {env_attr} -> {target_path} = {val}")
                except Exception as e:
                    logger.warning(f"Failed to apply env setting {env_attr}: {e}")

    def _apply_api_keys_from_env(self, soul_raw: dict):
        """
        专用：应用 API Key 覆盖 logic
        从 EnvSettings 安全地读取 keys，并注入到 soul_raw 配置字典。
        优于 secrets.yaml
        """
        providers = soul_raw.get("providers")
        if not isinstance(providers, dict):
            return

        # 映射逻辑：Provider Name -> EnvSettings Attribute
        # 这里硬编码映射逻辑是安全的，因为 env_settings 此处是 Source of Truth
        key_mapping = {
            "openai": env_settings.OPENAI_API_KEY,
            "deepseek": env_settings.DEEPSEEK_API_KEY,
            "qwen": env_settings.QWEN_API_KEY or env_settings.DASHSCOPE_API_KEY,
        }

        for provider_name, api_key in key_mapping.items():
            if api_key and provider_name in providers:
                if isinstance(providers[provider_name], dict):
                    providers[provider_name]["api_key"] = api_key


# 全局单例实例
global_config = ConfigManager()

