from pydantic import BaseModel, Field

class AppConfig(BaseModel):
    """
    应用全局配置模型
    """
    app_name: str = "Cradle_Selrena"
    version: str = "0.1.0"
    debug: bool = False

class AsrConfig(BaseModel):
    """语音识别配置 (FunASR/SenseVoice)"""
    enabled: bool = Field(default=True, description="是否启用本地ASR")
    model_dir: str = Field(
        default="iic/SenseVoiceSmall", 
        description="模型名称或本地路径 (ModelScope ID)"
    )
    device: str = Field(
        default="cuda", 
        description="推理设备: cuda, cpu"
    )
    quantize: bool = Field(default=True, description="是否启用量化 (int8/fp16)")
    use_itn: bool = Field(default=True, description="输出文本规范化 (ITN)")

class AudioPerceptionConfig(BaseModel):
    sample_rate: int = 16000
    chunk_size: int = 1024
    device_index: int | None = None
    asr: AsrConfig = Field(default_factory=AsrConfig)

class VisionPerceptionConfig(BaseModel):
    capture_interval: float = 5.0

class PerceptionConfig(BaseModel):
    """感知层配置"""
    audio: AudioPerceptionConfig = Field(default_factory=AudioPerceptionConfig)
    vision: VisionPerceptionConfig = Field(default_factory=VisionPerceptionConfig)


class TTSConfig(BaseModel):
    engine: str = "edge-tts" # gpt-sovits | edge-tts
    
    # Common
    output_dir: str = "./runtime/tts"
    auto_play: bool = True
    save_audio: bool = True
    audio_format: str = "wav" 

    # GPT-SoVITS Params (High Quality Clone)
    api_url: str = "http://127.0.0.1:9880"
    character_map_path: str = "./configs/voice_presets.json" # 情感音频映射表

    # EdgeTTS Params (Legacy)
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+3%"
    volume: str = "+0%"
    pitch: str = "+4Hz"

class VTSConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8001

class PresentationConfig(BaseModel):
    """表达层配置"""
    tts: TTSConfig = Field(default_factory=TTSConfig)
    vts: VTSConfig = Field(default_factory=VTSConfig)


class MemoryConfig(BaseModel):
    vector_store_path: str = "./data/vector_store"


class SystemSettings(BaseModel):
    """
    系统级配置根节点 (Infrastructure)
    对应 configs/settings.yaml
    包含了驱动、硬件参数、应用行为等不随人格变化的基础设施配置
    """
    app: AppConfig = Field(default_factory=AppConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    presentation: PresentationConfig = Field(default_factory=PresentationConfig)
