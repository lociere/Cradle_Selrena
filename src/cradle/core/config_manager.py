import yaml
import os
import copy
from pathlib import Path
from typing import Dict, Any, Callable, List, Tuple
from cradle.schemas import SystemSettings, SoulConfig, AppConfig, LLMConfig, PersonaConfig
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from dotenv import load_dotenv

# 加载 .env 环境变量文件，使其可用于 os.getenv
load_dotenv()

class ConfigManager:
    """
    统一配置管理中心 (Single Source of Truth)
    
    结构优化：
    分离系统基础配置 (SystemSettings) 与核心生命配置 (SoulConfig)。
    
    1. SystemSettings: 对应 configs/settings.yaml (基础设施、驱动、APP行为)
    2. SoulConfig:     对应 configs/persona.yaml (身份、记忆、认知模型)
    """
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
            try:
                pass
                # logger.debug(f"已加载核心: {self.persona.name}")
            except Exception:
                pass
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

    def get(self) -> SystemSettings:
        """获取当前系统配置 (Deprecated: prefer get_system or get_soul)"""
        return self.sys_config

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
        # 路由逻辑
        is_soul_config = False
        target_path = key_path

        if key_path.startswith("soul."):
            is_soul_config = True
            target_path = key_path.replace("soul.", "", 1)
        elif key_path.startswith("persona.") or key_path.startswith("providers."):
            is_soul_config = True
        
        # 1. 预校验
        try:
            if is_soul_config:
                test_raw = copy.deepcopy(self.raw_soul)
                self._set_nested_value(test_raw, target_path, value)
                SoulConfig(**test_raw)
            else:
                test_raw = copy.deepcopy(self.raw_sys)
                self._set_nested_value(test_raw, target_path, value)
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
        # --- 1. System Config (settings.yaml) ---
        sys_raw = {}
        self._merge_yaml(sys_raw, self.config_dir / "settings.yaml")
        # Secrets 也可以覆盖系统配置 (如数据库密码)
        self._merge_yaml(sys_raw, self.config_dir / "secrets.yaml")
        
        # --- 2. Soul Config (soul.yaml) ---
        soul_raw = {}
        # 读取 soul.yaml
        soul_file_data = {}
        if ProjectPath.SOUL_CONFIG.exists():
            with open(ProjectPath.SOUL_CONFIG, 'r', encoding='utf-8') as f:
                soul_file_data = yaml.safe_load(f) or {}
        
        # [MIGRATION] 智能判断：如果是旧的纯 PersonaConfig 结构（只有 name, role 等），需要包裹
        if soul_file_data and "persona" not in soul_file_data and "providers" not in soul_file_data:
            # 假设这是旧版只有 Persona 字段的文件
            soul_raw["persona"] = soul_file_data
        else:
            # 是新的 SoulConfig 结构
            self._deep_merge(soul_raw, soul_file_data)

        # Secrets 覆盖 Soul (如 LLM API Key)
        self._merge_yaml(soul_raw, self.config_dir / "secrets.yaml")

        # --- 3. Env Overrides ---
        # System: SELRENA_APP_DEBUG -> app.debug
        self._apply_env_overrides(sys_raw, prefix="SELRENA")
        
        # Soul: SELRENA_PERSONA_NAME -> persona.name
        self._apply_env_overrides(soul_raw, prefix="SELRENA")
        
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

    def _save_to_source_file(self, key_path: str, value: Any):
        """
        根据路径路由写入 settings.yaml 或 soul.yaml
        """
        # 判定目标文件
        is_soul = False
        inner_key = key_path

        if key_path.startswith("soul."):
            is_soul = True
            inner_key = key_path.replace("soul.", "", 1)
        elif key_path.startswith("persona.") or key_path.startswith("providers.") or key_path == "active_provider":
            is_soul = True
        
        target_file = ProjectPath.SOUL_CONFIG if is_soul else (self.config_dir / "settings.yaml")
        
        # 读取 -> 修改 -> 写入
        data = {}
        if target_file.exists():
            with open(target_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # 特殊处理：如果写入 SoulConfig 但文件是旧格式（纯 PersonaConfig），且我们在更新 Persona 字段
        if is_soul and "persona" not in data and "providers" not in data and inner_key.startswith("persona."):
            # 这是一个纯 Persona 文件，我们要更新 key="name" (from persona.name)
            layout_key = inner_key.replace("persona.", "", 1)
            self._set_nested_value(data, layout_key, value)
        else:
             self._set_nested_value(data, inner_key, value)
        
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

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
        """仅同步 SystemSettings 到 settings.yaml"""
        settings_path = self.config_dir / "settings.yaml"
        try:
            schema_defaults = SystemSettings().model_dump(mode='json')
            
            current_data = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    current_data = yaml.safe_load(f) or {}

            updated, final_data = self._fill_missing_defaults(current_data, schema_defaults)

            if updated:
                logger.info("检测到 settings.yaml 缺少新配置项，正在回填...")
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                with open(settings_path, 'w', encoding='utf-8') as f:
                    yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.warning(f"自动同步配置失败: {e}")

    def _fill_missing_defaults(self, current: dict, defaults: dict) -> Tuple[bool, dict]:
        """
        递归对比，将 defaults 中有但 current 中没有的键补入 current。
        返回 (is_updated, new_dict)
        """
        updated = False
        # 为了不破坏原有引用，我们操作 current 的引用（in-place modification 也可以，但逻辑上要注意）
        # 这里直接修改 current 字典对象
        
        for key, default_val in defaults.items():
            if key not in current:
                # 情况A: 整个 key 缺失 -> 直接补全默认值
                current[key] = default_val
                updated = True
            elif isinstance(default_val, dict) and isinstance(current.get(key), dict):
                # 情况B: key 存在且都是字典 -> 递归检查子节点
                sub_updated, _ = self._fill_missing_defaults(current[key], default_val)
                if sub_updated:
                    updated = True
            # 情况C: key 存在但类型不匹配或是叶子节点 -> 尊重用户配置，不覆盖
        
        return updated, current

    # -------------------------------------------------------------------------
    # 辅助方法 (Helpers)
    # -------------------------------------------------------------------------

    def _merge_yaml(self, target: dict, path: Path):
        """读取并合并 YAML 文件到目标字典中"""
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self._deep_merge(target, data)
        except Exception as e:
            logger.warning(f"读取配置 {path.name} 失败: {e}")

    def _merge_soul_legacy(self, target: dict):
        """(Deprecated) 专门处理旧版 Persona 配置文件的合并逻辑"""
        path = ProjectPath.SOUL_CONFIG
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                # 映射规则: 文件根节点 -> 配置树的 soul.persona 节点
                soul = target.setdefault("soul", {})
                self._deep_merge(soul.setdefault("persona", {}), data)

    def _set_nested_value(self, d: dict, key_path: str, value: Any):
        """
        根据点分路径设置嵌套字典的值。
        例如: "a.b.c" -> d['a']['b']['c'] = value
        """
        keys = key_path.split('.')
        current = d
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value

    def _deep_merge(self, source: dict, dest: dict):
        """
        递归合并两个字典。
        将 dest 中的内容合并到 source 中，如果是字典则递归合并，否则直接覆盖。
        """
        for key, value in dest.items():
            if isinstance(value, dict) and key in source and isinstance(source[key], dict):
                self._deep_merge(source[key], value)
            else:
                source[key] = value

    def _apply_env_overrides(self, data: dict, prefix: str = "SELRENA"):
        """
        递归应用环境变量覆盖配置。
        环境变量格式为：前缀_层级_键名 (例如 SELRENA_SOUL_LLM_TEMPERATURE)
        """
        for key, value in list(data.items()):
            current_prefix = f"{prefix}_{key.upper()}"
            if isinstance(value, dict):
                self._apply_env_overrides(value, current_prefix)
            else:
                # 特殊字段的映射逻辑
                if key == "api_key" and prefix.endswith("LLM"):
                     # 优先尝试读取标准的 AI API KEY
                     env_val = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
                     if env_val: data[key] = env_val
                     continue

                env_val = os.getenv(current_prefix)
                if env_val is not None:
                     # 简单的类型推断，将字符串转换为对应的 Python 类型
                    if env_val.lower() == 'true': env_val = True
                    elif env_val.lower() == 'false': env_val = False
                    elif env_val.isdigit(): env_val = int(env_val)
                    elif self._is_float(env_val): env_val = float(env_val)
                    data[key] = env_val

    def _is_float(self, s: str) -> bool:
        """检查字符串是否为有效的浮点数"""
        try:
            float(s)
            return True
        except ValueError:
            return False

# 全局单例实例
global_config = ConfigManager()

