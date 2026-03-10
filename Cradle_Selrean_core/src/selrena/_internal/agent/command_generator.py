# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import Any

from selrena._internal.ports.agent import AgentPort


class CommandGenerator:
    """用于构造并发送 MCP 命令的辅助类。

    这个辅助类不会直接发送命令，而是通过
    提供的 ``AgentPort`` 实例来完成。抽象的好处在于
    可以在单元测试中替换不同实现。
    """

    def __init__(self, port: AgentPort):
        self._port = port

    async def build(self, intent: str, tools: list[dict[str, Any]]) -> None:
        """根据意图和工具列表构造命令并发送。

        当前实现非常简单，仅包含意图和工具两个字段。
        """
        command = {"intent": intent, "tools": tools}
        await self._port.send_command(command)
