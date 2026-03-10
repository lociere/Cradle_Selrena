"""插件基类，定义扩展点/接口。"""

class BasePlugin:
    def activate(self):
        pass

    def deactivate(self):
        pass
