# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from .base import BaseBrainBackend


class LlamaCppEmbeddedBackend(BaseBrainBackend):
    """åµå
    ¥å¼?LlamaCpp å¼æçç¤ºä¾åç«¯ã?



        ç¨äºæ¬å°é¨ç½²åºæ¯ï¼å½åä¸ºå ä½å®ç°ã?

    """

    async def generate(self, prompt: str) -> str:

        return f"[embedded] {prompt[:20]}..."
