"""配置加载模块：从内核接收配置，无文件读写。
"""

class ConfigLoader:
    def load(self, data: dict):
        self.data = data
        return self.data
