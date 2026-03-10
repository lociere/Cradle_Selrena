"""OC 全局单例 SelfEntity。

按照架构文档该类管理 self_id、人设、生命时间线、成长轨迹等。
"""

from __future__ import annotations


class SelrenaSelfEntity:
    def __init__(self):
        self.self_id = None
        # 四层人设、时间线、成长状态等等
