"""进程内事件总线，占位实现。"""

class EventBus:
    def register_handler(self, event_type: str, handler):
        pass

    async def publish(self, event_type: str, payload):
        pass
