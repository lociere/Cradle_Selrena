"""MCP 协议封装：仅生成工具指令，不执行。
"""

class MCPClient:
    def generate_command(self, intent: str, **kwargs):
        return {}
