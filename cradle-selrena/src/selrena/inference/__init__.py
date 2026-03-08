"""Inference layer exports during migration."""

from .llm import LLMBackend, DummyLLM, OpenAILLM, LocalLLM
from .audio import STTBackend, TTSBackend
from .vision import VisionBackend

# engines exports (formerly engine_pool)
from .engines.base import BaseBrainBackend
from .engines.embedded import LlamaCppEmbeddedBackend
from .engines.remote import OpenAIRemoteBackend
from .engines.router import BrainFactory, HybridBrainRouter
from .engines.utils.preprocessor import MultimodalPreprocessor
from .engines.utils.prompt_builder import PromptBuilder

__all__: list[str] = [
    "LLMBackend", "DummyLLM", "OpenAILLM", "LocalLLM",
    "STTBackend", "TTSBackend",
    "VisionBackend",
    "BaseBrainBackend", "LlamaCppEmbeddedBackend", "OpenAIRemoteBackend",
    "BrainFactory", "HybridBrainRouter",
    "MultimodalPreprocessor", "PromptBuilder",
]
