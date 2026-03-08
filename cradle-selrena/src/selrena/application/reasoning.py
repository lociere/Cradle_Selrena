"""推理服务 - 多模态推理编排（迁移自 cradle_selrena_core）"""

from typing import Optional

from selrena.domain.persona import Persona
from selrena.inference.llm import LLMBackend
from selrena.inference.vision import VisionBackend
from selrena.inference.audio import STTBackend, TTSBackend
from selrena.utils.logger import logger


class ReasoningService:
    """
    推理服务
    
    负责：
    1. 文本推理（LLM）
    2. 视觉理解（Image Caption）
    3. 语音识别（STT）
    4. 语音合成（TTS）
    """
    
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
        logger.info("ReasoningService 初始化完成")
    
    async def reason(self, text: str, context: Optional[str] = None) -> str:
        """纯文本推理"""
        prompt = text
        if context:
            prompt = f"{context}\n\n{text}"
        return await self.llm.generate(prompt)
    
    async def perceive_image(self, image_path: str) -> str:
        """理解图片内容"""
        if not self.vision:
            return "视觉模块未启用"
        return await self.vision.describe(image_path)
    
    async def transcribe_audio(self, audio_path: str) -> str:
        """语音转文字"""
        if not self.stt:
            return "STT 模块未启用"
        return await self.stt.transcribe(audio_path)
    
    async def synthesize_speech(self, text: str, output_path: str) -> str:
        """文字转语音"""
        if not self.tts:
            return ""
        return await self.tts.synthesize(text, output_path)
