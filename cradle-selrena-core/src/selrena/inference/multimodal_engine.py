"""用于图片/语音等多模态推理的抽象引擎。"""

class MultimodalEngine:
    async def process_image(self, image_bytes: bytes) -> str:
        return ""

    async def process_audio(self, audio_bytes: bytes) -> str:
        return ""
