# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from abc import ABC, abstractmethod
from typing import Any


class AgentPort(ABC):
    """Port used by the Agent layer to send MCP commands to the kernel.

    The Python Agent implementation is responsible for *generating* the
    command structures; the kernel performs the actual execution. Keeping
    this as an abstract port lets us mock the kernel during tests and
    maintain full language isolation.
    """

    @abstractmethod
    async def send_command(self, command: dict[str, Any]) -> None:
        """Send a dictionary representing an MCP command to the kernel.

        The exact schema of ``command`` is defined by the global protocol
        package; the port does not inspect the contents.
        """
        ...
