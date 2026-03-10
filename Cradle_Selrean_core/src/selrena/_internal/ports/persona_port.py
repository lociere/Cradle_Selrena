# 人格数据访问端口定义
from abc import ABC, abstractmethod

from selrena._internal.domain.persona import Persona


class PersonaPort(ABC):
    """人格数据的增删改查接口。

    持久化方式可以是文件、数据库或远程服务。
    """

    @abstractmethod
    async def load_persona(self, name: str) -> Persona:
        """根据名称返回 persona 对象。"""

    @abstractmethod
    async def save_persona(self, persona: Persona) -> None:
        """保存 persona 对象。"""
