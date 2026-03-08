from typing import Any, List


class PromptBuilder:
    @staticmethod
    def build(messages: List[Any]) -> dict:
        """构建向 LLM 发送的 payload。

        接受任意对象，只要具有 `dict()` 方法或可转换为字符串。
        """
        serialized: list[Any] = []
        for m in messages:
            if hasattr(m, "dict"):
                serialized.append(m.dict())
            else:
                serialized.append(m)
        return {"messages": serialized}
