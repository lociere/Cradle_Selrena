from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """
    全局环境变量定义 (Single Source of Truth for Environment Variables)
    所有支持的环境变量必须在此处定义，以获得类型检查和文档支持。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # 忽略未定义的变量，避免报错
    )

    # --- System ---
    SELRENA_APP_DEBUG: bool = Field(False, description="是否启用调试模式")
    SELRENA_LOG_LEVEL: str = Field("INFO", description="日志级别")

    # --- Napcat (QQ Bot) ---
    SELRENA_NAPCAT_ENABLE: Optional[bool] = Field(
        None, description="是否启用 Napcat")
    SELRENA_NAPCAT_ACCOUNT: Optional[int] = Field(
        None, description="Napcat 账号")
    SELRENA_NAPCAT_TOKEN: Optional[str] = Field(
        None, description="Napcat Token")

    # --- Perception ---
    SELRENA_PERCEPTION_STRICT_WAKE_WORD: Optional[bool] = Field(
        None, description="严格唤醒词模式")
    SELRENA_PERCEPTION_VISION_ENABLED: Optional[bool] = Field(
        None, description="是否启用视觉能力")

    # --- Soul Strategy ---
    SELRENA_SOUL_STRATEGY_API_PROVIDER: Optional[str] = Field(
        None, description="云端 API Provider")
    SELRENA_SOUL_STRATEGY_FALLBACK_TO_LOCAL: Optional[bool] = Field(
        None, description="是否允许回退到本地")

    # --- API Keys (Explicitly Defined) ---
    # 遵循 <PROVIDER>_API_KEY 的命名规范
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API Key")
    DEEPSEEK_API_KEY: Optional[str] = Field(
        None, description="DeepSeek API Key")
    QWEN_API_KEY: Optional[str] = Field(
        None, description="Qwen/DashScope API Key")
    DASHSCOPE_API_KEY: Optional[str] = Field(
        None, description="Alias for Qwen API Key")

    # --- Other Secrets ---
    VTS_TOKEN: Optional[str] = Field(None, description="VTS Token")


# 全局单例
env_settings = EnvSettings()
