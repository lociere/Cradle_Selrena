# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from .base import BaseBrainBackend


class OpenAIRemoteBackend(BaseBrainBackend):
    """è¿ç¨åç«¯ç¤ºä¾ï¼å¯ç¨äº OpenAI æç±»ä¼¼äºæå¡ã?



        å½åä¸ºå ä½å®ç°ï¼ä»
    è¿åå¸¦åç¼çæç¤ºçæ®µã?

    """

    async def generate(self, prompt: str) -> str:

        return f"[remote] {prompt[:20]}..."
