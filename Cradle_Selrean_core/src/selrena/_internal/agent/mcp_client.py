# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import Any


class MCPClient:
    """用于构建 MCP 命令负载的轻量级助手。

    Agent 会通过 AgentPort 向内核发送字典，本类负责构造该字典、
    执行简单校验，并维护先前工具响应的历史。
    """

    def __init__(self):
        self._history: list[dict[str, Any]] = []

    def add_tool_response(self, response: Any) -> None:
        """向历史记录添加工具执行结果。"""
        self._history.append({"tool_response": response})

    def create_command(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """构建包含操作和历史的命令负载。"""
        cmd = {"actions": actions, "history": self._history.copy()}
        # 此处可添加 schema 验证
        return cmd
