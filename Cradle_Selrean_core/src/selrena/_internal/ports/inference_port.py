# 推理后端接口定义
from typing import Any, Protocol


class InferencePort(Protocol):
    """可选的推理后端接口，便于接入外部服务。

    大多数服务直接与 `inference` 层交互，此协议仅作适配。
    """

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """根据提示生成文本。"""
