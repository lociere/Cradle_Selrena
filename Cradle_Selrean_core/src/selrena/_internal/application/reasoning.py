# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""推理服务 - 多模态推理协调。"""

from typing import Optional

from selrena._internal.domain.persona import Persona
from selrena._internal.inference.llm import LLMBackend
from selrena._internal.inference.vision import VisionBackend
from selrena._internal.inference.audio import STTBackend, TTSBackend
from loguru import logger


class ReasoningService:
    """提供文本推理、图像说明、STT/TTS 集成。"""

    def __init__(
        self,
        llm: LLMBackend,
        vision: Optional[VisionBackend] = None,
        stt: Optional[STTBackend] = None,
        tts: Optional[TTSBackend] = None,
    ):
        self.llm = llm
        self.vision = vision
        self.stt = stt
        self.tts = tts
        logger.info("ReasoningService initialized")

    async def reason(self, text: str, context: Optional[str] = None) -> str:
        """通过 LLM 执行纯文本推理。"""
        prompt = text
        if context:
            prompt = f"{context}\n\n{text}"
        return await self.llm.generate(prompt)

    async def perceive_image(self, image_path: str) -> str:
        """使用视觉后端描述图像。"""
        if not self.vision:
            return "vision module not available"
        return await self.vision.describe(image_path)

    async def transcribe_audio(self, audio_path: str) -> str:
        """使用 STT 将音频转为文本。"""
        if not self.stt:
            return "STT module not available"
        return await self.stt.transcribe(audio_path)

    async def synthesize_speech(self, text: str, output_path: str) -> str:
        """通过 TTS 将文本转语音。"""
        if not self.tts:
            return ""
        return await self.tts.synthesize(text, output_path)
