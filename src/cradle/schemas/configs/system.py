from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    """
    应用全局配置模型
    """
    model_config = ConfigDict(extra="ignore")

    app_name: str = Field(default="Cradle_Selrena", description="应用名称")
    version: str = "0.1.0"
    debug: bool = False


class AsrConfig(BaseModel):
    """语音识别配置 (FunASR/SenseVoice)"""
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用本地ASR")
    model_dir: str = Field(
        default="iic/SenseVoiceSmall",
        description="模型名称或本地路径 (ModelScope ID)"
    )
    device: Literal["cuda", "cpu", "mps"] = Field(
        default="cuda",
        description="推理设备: cuda, cpu"
    )
    quantize: bool = Field(default=True, description="是否启用量化 (int8/fp16)")
    use_itn: bool = Field(default=True, description="输出文本规范化 (ITN)")


class AudioPerceptionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用麦克风监听与 ASR")
    sample_rate: int = Field(default=16000, ge=8000, le=192000)
    chunk_size: int = Field(default=1024, ge=128, le=16384)
    device_index: int | None = Field(default=None, ge=0)
    asr: AsrConfig = Field(default_factory=AsrConfig)


class VisionPerceptionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用视觉感知")
    capture_interval: float = Field(default=5.0, ge=0.1, le=3600.0)


class PerceptionConfig(BaseModel):
    """感知层配置"""
    model_config = ConfigDict(extra="ignore")

    audio: AudioPerceptionConfig = Field(default_factory=AudioPerceptionConfig)
    vision: VisionPerceptionConfig = Field(
        default_factory=VisionPerceptionConfig)
    accepted_modalities: list[Literal["text", "visual"]] = Field(
        default_factory=lambda: ["text"],
        description="允许进入 synapse 的输入模态白名单；默认仅文本。"
    )
    strict_wake_word: bool = Field(
        default=False, description="严格唤醒模式：仅包含唤醒词的输入才能进入意识流")
    wake_timeout_sec: float = Field(
        default=30.0, ge=1.0, le=600.0, description="非严格模式下的注意力保持时长（秒）")
    non_text_chain_timeout_sec: float = Field(
        default=30.0,
        ge=1.0,
        le=600.0,
        description="非文本跟随窗口：在唤醒词后该时长内，非文本输入可连续进入意识流并连锁续期。",
    )


class TTSConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用 TTS 输出")
    engine: Literal["gpt-sovits", "edge-tts"] = "edge-tts"

    # Common
    output_dir: str = "./runtime/tts"
    auto_play: bool = True
    save_audio: bool = True
    audio_format: Literal["wav", "mp3", "ogg"] = "wav"

    # GPT-SoVITS Params (High Quality Clone)
    api_url: str = "http://127.0.0.1:9880"
    character_map_path: str = "./configs/voice_presets.json"  # 情感音频映射表

    # EdgeTTS Params (Legacy)
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class VTSConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=False, description="是否启用虚拟形象桥接 (VTS)")
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1, le=65535)


class PresentationConfig(BaseModel):
    """表达层配置"""
    model_config = ConfigDict(extra="ignore")

    tts: TTSConfig = Field(default_factory=TTSConfig)
    vts: VTSConfig = Field(default_factory=VTSConfig)


class ModelManagerConfig(BaseModel):
    """全局模型管理策略"""
    model_config = ConfigDict(extra="ignore")

    auto_download: bool = Field(
        default=False, description="全局自动下载模型的开关（安全默认：关闭）")
    size_threshold_mb: int = Field(
        default=10, ge=1, le=10240, description="判断单文件是否为有效权重的最小大小（MB）")
    whitelist: list[str] = Field(
        default_factory=list, description="允许自动下载的模型仓库白名单（空表示无限制）")


class NapcatConfig(BaseModel):
    """Napcat/OneBot11 WebSocket 配置

    当前仅实现 **服务器模式**：Selrena 本身担当 OneBot 主机，
    Napcat 客户端连接并推送事件。以后若需实现客户端功能
    可以在此添加额外字段。
    """
    model_config = ConfigDict(extra="ignore")

    enable: bool = Field(default=False, description="是否启用 Napcat 支持")
    listen_port: int = Field(
        default=6101, ge=1, le=65535, description="本地监听端口")
    token: str = Field(default="", description="可选的连接验证令牌，发送时附加在子协议中")
    silent_record_window: int = Field(default=50, description="静默记录窗口大小")


class SystemSettings(BaseModel):
    """
    系统级配置根节点 (Infrastructure)
    对应 configs/settings.yaml + configs/vessel/*.yaml
    包含了驱动、硬件参数、应用行为等不随人格变化的基础设施配置
    """
    model_config = ConfigDict(extra="ignore")

    app: AppConfig = Field(default_factory=AppConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    presentation: PresentationConfig = Field(
        default_factory=PresentationConfig)
    model_manager: ModelManagerConfig = Field(
        default_factory=ModelManagerConfig)
    napcat: NapcatConfig = Field(default_factory=NapcatConfig)
