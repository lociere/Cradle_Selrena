"""日志生成：结构化日志，无文件写入。"""

class Logger:
    def info(self, msg: str, **kwargs):
        print(msg, kwargs)
    def error(self, msg: str, **kwargs):
        print(msg, kwargs)
