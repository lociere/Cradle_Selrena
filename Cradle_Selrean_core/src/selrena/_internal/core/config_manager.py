# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""AI 子系统的配置管理模块。

本模块定义了一组 pydantic 模型来表示全局配置，
并提供一个单例管理器，可用于从内核同步配置数据。
"""

from typing import Any, Dict, Optional, Callable
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    app_name: str = Field(default="Cradle_Selrena")
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)


class BrainConfig(BaseModel):
    strategy: dict = Field(default_factory=dict)
    persona: dict = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    napcat: dict = Field(default_factory=dict)  # vessel 层配置等


class ConfigManager:
    """全局配置的单例管理器。"""

    _instance: Optional["ConfigManager"] = None
    _config: Optional[GlobalConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = GlobalConfig()

    async def sync_from_kernel(
        self, sys_config: Optional[dict] = None, brain_config: Optional[dict] = None
    ) -> None:
        """根据内核提供的数据更新内部配置。

        Args:
            sys_config: 系统级别配置字典。
            brain_config: 大脑相关配置字典。
        """
        if sys_config:
            for k, v in sys_config.items():
                setattr(self._config, k, v)
        if brain_config:
            for k, v in brain_config.items():
                setattr(self._config.brain, k, v)

    def get_config(self) -> GlobalConfig:
        assert self._config is not None
        return self._config


# 模块级单例
global_config = ConfigManager()
