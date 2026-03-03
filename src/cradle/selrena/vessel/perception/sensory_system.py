from typing import Any, Dict, List, Optional, Tuple, Union

from cradle.schemas.configs.soul import SoulConfig
from cradle.utils.logger import logger

from .vision.visual_cortex import VisualCortex, VisualSignal


class SensorySystem:
    """
    sensory system vessel component

    Architecture V3 (Multimodal Pass-through):
    The Vessel handles 'Sensation' (Acquiring signals), not 'Perception' (Understanding meaning).
    It passes raw neural signals (VisualSignal) to the Soul.
    """

    def __init__(self, config: SoulConfig):
        self.config = config
        self.visual_cortex = VisualCortex(config)

    async def initialize(self):
        try:
            await self.visual_cortex.initialize()
            logger.info("[SensorySystem] Retina connected.")
        except Exception as e:
            logger.warning(
                f"[SensorySystem] Sensory initialization incomplete: {e}")

    async def cleanup(self):
        await self.visual_cortex.cleanup()

    async def perceive(self, message: Dict[str, str]) -> Dict[str, Any]:
        """
        感官系统信息总线 (Sensory Bus):
        Raw Input -> Modality Extraction (Vision, Audio...) -> Multimodal LLM Payload

        这个管道允许将不同模态的信号叠加成大模型所需要的输入数组。
        """
        role = message.get("role", "user")
        content = message.get("content", "")

        result = message.copy()

        # 保证只转化用户的文本输入
        if role != "user" or not content or not isinstance(content, str):
            return result

        processed_text = content
        llm_content_parts = []
        is_multimodal = False

        # --- 1. 视觉通道 (Visual Cortex) ---
        if self.visual_cortex.has_signal(content):
            logger.debug(
                "[SensorySystem] Visual signal detected, engaging retina...")
            try:
                # 皮层负责“感受”：下载/读取图片 -> 转化为原始 Base64
                processed_text, signals = await self.visual_cortex.process(processed_text)

                if signals:
                    is_multimodal = True
                    for signal in signals:
                        llm_content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{signal.media_type};base64,{signal.image_base64}"
                            }
                        })
                    logger.debug(
                        f"[SensorySystem] Signal transduced: {len(signals)} images embedded.")
            except Exception as e:
                logger.error(f"[SensorySystem] Visual sensation failed: {e}")

        # --- 2. 听觉通道 (Auditory Cortex - 扩展接口预留) ---
        # 说明：这里预留对“原生语音输入”（如 GPT-4o-audio）的支持
        # if hasattr(self, 'auditory_cortex') and self.auditory_cortex.has_signal(content):
        #     processed_text, audio_signals = await self.auditory_cortex.process(processed_text)
        #     if audio_signals:
        #         is_multimodal = True
        #         for sig in audio_signals:
        #             llm_content_parts.append({
        #                 "type": "input_audio",
        #                 "input_audio": {"data": sig.audio_base64, "format": sig.format}
        #             })

        # --- 3. 触觉/文件通道 (File Cortex - 扩展接口预留) ---
        # 说明：预留对文档、PDF、代码补丁等多模态输入的直接内嵌支持
        # if hasattr(self, 'file_cortex') and self.file_cortex.has_signal(content):
        #     # ...

        # --- 4. 嗅觉/环境状态 (Environment Cortex - 扩展接口预留) ---
        # 系统状态、当前时间、温度等可以作为外接设备的状态注入

        # --- 信号聚合 (Integration) ---
        if is_multimodal:
            # 文本永远放在第一位，包含修剪后的原文（如：URL 已被替换为占位符）
            llm_content_parts.insert(
                0, {"type": "text", "text": processed_text})
            result["content"] = llm_content_parts
            # 标记为多模态，方便 Soul 的 Brain 路由器识别
            result["is_multimodal"] = True
        else:
            # 如果没有截获任何多模态特征，保持普通文本
            result["content"] = processed_text

        return result
