"""注册可用工具及其参数定义。"""

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name: str, schema: dict):
        self.tools[name] = schema
