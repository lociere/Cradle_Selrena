# 该文件已格式化，内部备注/注释请使用中文说明
"""Agent 层辅助工具与接口导出。

本包包含 Agent 模块的 domain、application 等子组件，负责构建
符合 MCP 规范的命令字典。Agent 本身并不直接与内核通信，所有
数据通过容器提供的 ``AgentPort`` 接口发送。
"""

from .command_generator import CommandGenerator

from .mcp_client import MCPClient

from .tool_registry import ToolRegistry

__all__ = ["CommandGenerator", "MCPClient", "ToolRegistry"]
