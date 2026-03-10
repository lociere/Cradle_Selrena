# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""推理层的导出接口（迁移期间使用）。"""

from .llm import LLMBackend, DummyLLM, OpenAILLM, LocalLLM
from .audio import STTBackend, TTSBackend
from .vision import VisionBackend

# 引擎池暴露后端和路由器
from .engine_pool import (
    BaseBrainBackend,
    LlamaCppEmbeddedBackend,
    OpenAIRemoteBackend,
    BrainFactory,
    HybridBrainRouter,
)

# 预处理器和提示构建器已移动到 text 子包
from selrena._internal.utils.text.preprocessor import MultimodalPreprocessor
from selrena._internal.utils.text.prompt_builder import PromptBuilder
from .sensory import SensorySystem

__all__: list[str] = [
    "LLMBackend",
    "DummyLLM",
    "OpenAILLM",
    "LocalLLM",
    "STTBackend",
    "TTSBackend",
    "VisionBackend",
    "BaseBrainBackend",
    "LlamaCppEmbeddedBackend",
    "OpenAIRemoteBackend",
    "BrainFactory",
    "HybridBrainRouter",
    "MultimodalPreprocessor",
    "PromptBuilder",
    "SensorySystem",
]
