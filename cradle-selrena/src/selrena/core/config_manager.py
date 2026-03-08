"""配置管理器 (Configuration Manager)

负责从内核同步配置，无本地文件读写。
遵循最小权限原则，仅提供配置读取接口。
"""

from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用配置模型"""
    app_name: str = Field(default="Cradle_Selrena")
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)


class BrainConfig(BaseModel):
    """核心大脑相关配置（替代旧的 soul）"""
    strategy: dict = Field(default_factory=dict)
    persona: dict = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    """全局配置模型"""
    app: AppConfig = Field(default_factory=AppConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    napcat: dict = Field(default_factory=dict)  # napcat / vessel settings etc

    # 更多节可以按需添加


class ConfigManager:
    """配置管理器"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[GlobalConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = GlobalConfig()
    
    async def sync_from_kernel(self, sys_config: dict | None = None, brain_config: dict | None = None) -> None:
        """
        从内核同步配置数据。

        Args:
            sys_config: 系统级配置字典（通常包含 app/napcat 等）
            brain_config: 大脑相关配置字典（包含 strategy/persona 等）
        """
        # TODO: 与实际内核通信。
        if sys_config:
            # 将系统部分合并到模型
            for k, v in sys_config.items():
                setattr(self._config, k, v)  # 直接赋值会转为dict字段
        if brain_config:
            # 保持兼容旧名
            if "soul" in brain_config:
                bc = brain_config["soul"]
            else:
                bc = brain_config
            self._config.brain.strategy = bc.get("strategy", {})
            self._config.brain.persona = bc.get("persona", {})
        self._notify_observers()
        print("[ConfigManager] 已同步配置")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（点分路径）。"""
        keys = key.split('.')
        value = self._config.dict()
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    # convenience accessors
    def get_system(self) -> AppConfig:
        """返回系统配置对象"""
        return self._config.app

    def get_brain(self) -> BrainConfig:
        """返回大脑配置对象（旧名 soul）"""
        return self._config.brain

    def add_observer(self, callback: Callable) -> None:
        """注册配置变更回调。"""
        if not hasattr(self, '_observers'):
            self._observers: list[Callable] = []
        self._observers.append(callback)

    def _notify_observers(self) -> None:
        if hasattr(self, '_observers'):
            for cb in list(self._observers):
                try:
                    cb()
                except Exception:
                    pass
    
    @property
    def config(self) -> GlobalConfig:
        """获取完整配置对象"""
        return self._config


# 全局配置实例
global_config = ConfigManager()
