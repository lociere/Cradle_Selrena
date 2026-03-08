"""Ports Layer - ??????????? cradle_selrena_core?"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from selrena.domain.memory import Memory
from selrena.domain.persona import Persona


class KernelPort(ABC):
    """
    ???? - AI ??????????????
    
    ?? AI ????????????????TS/Rust?????????
    """
    
    @abstractmethod
    async def send_message(self, text: str, emotion: Optional[str] = None) -> None:
        """????????? QQ?UI ??"""
        pass
    
    @abstractmethod
    async def play_audio(self, audio_path: str) -> None:
        """????"""
        pass
    
    @abstractmethod
    async def capture_screen(self) -> str:
        """???????????"""
        pass
    
    @abstractmethod
    async def read_file(self, path: str) -> str:
        """??????"""
        pass
    
    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """??????"""
        pass


class MemoryPort(ABC):
    """??????"""
    
    @abstractmethod
    async def save_memory(self, memory: Memory) -> None:
        """????"""
        pass
    
    @abstractmethod
    async def retrieve_memories(self, query: str, n_results: int = 5) -> list[Memory]:
        """??????"""
        pass
    
    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """????"""
        pass


class Personaport(ABC):
    """??????"""
    
    @abstractmethod
    async def load_persona(self, name: str) -> Persona:
        """??????"""
        pass
    
    @abstractmethod
    async def save_persona(self, persona: Persona) -> None:
        """??????"""
        pass


__all__ = [
    "KernelPort",
    "MemoryPort",
    "Personaport",
]
