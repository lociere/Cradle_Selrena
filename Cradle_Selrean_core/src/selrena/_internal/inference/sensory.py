# 该文件已格式化，内部备注/注释请使用中文说明
from typing import Any, Dict

from selrena._internal.utils.text.preprocessor import MultimodalPreprocessor


class SensorySystem:
    """感知系统：负责预处理来自外部的数据。

    本类不会直接执行 STT、OCR 等操作，而是对各种原始载荷
    （文字、图像、音频、混合物）做统一格式化，输出包含
    `content` 字段的字典，并指示是否包含视觉信息。
    这让后续模块（记忆、推理）无需关心数据格式。
    """

    def __init__(self, config: Any = None):
        self.config = config

    async def initialize(self) -> None:
        # 占位符：可用于异步加载模型或资源
        pass

    async def cleanup(self) -> None:
        # 占位符：释放资源
        pass

    async def perceive(self, raw: Any) -> Dict[str, Any]:
        """对原始数据进行感知处理。

        参数:
            raw: 来自外部的原始载荷，可以是 dict 或其他结构。
        返回值:
            包含键 `content`（文本或列表）、`has_visual`、`valid` 等。
        """
        text, has_visual, is_valid = MultimodalPreprocessor.validate_ingress_payload(
            raw
        )
        content = raw.get("content") if isinstance(raw, dict) else text
        if not content:
            content = text
        return {"content": content, "has_visual": has_visual, "valid": is_valid}
