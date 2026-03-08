"""Ports layer defines abstract interfaces used by the Python core.

Concrete adapters implement these ports; business logic depends only on
these abstractions.  Add new ports here when additional infrastructure
capabilities are required (e.g. inference engines).
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

from selrena.domain.memory import Memory
from selrena.domain.persona import Persona


class KernelPort(ABC):
    """Interface provided by the TS/Rust kernel to Python services.

    All methods should be non‑blocking and language‑agnostic; the kernel
    implements them by emitting events on the global protocol bus.
    """

    @abstractmethod
    async def send_message(self, text: str, emotion: Optional[str] = None) -> None:
        """Send a text message to the front end or chat adapter."""

    @abstractmethod
    async def play_audio(self, audio_path: str) -> None:
        """Request the kernel to play a local audio file."""

    @abstractmethod
    async def capture_screen(self) -> str:
        """Take a screenshot and return the file path."""

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read and return contents of a file accessible by the kernel."""

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """Write text content to a file via the kernel."""


class MemoryPort(ABC):
    """Abstract storage interface used by the memory services.

    Current implementation is filesystem‑based; can be replaced with a
    database or vector store.
    """

    @abstractmethod
    async def save_memory(self, memory: Memory) -> None:
        """Persist a Memory object."""

    @abstractmethod
    async def retrieve_memories(self, query: str, n_results: int = 5) -> list[Memory]:
        """Return a list of memories relevant to the query."""

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """Remove a memory by identifier."""


class InferencePort(Protocol):
    """Optional port interface for plugging in external inference backends.

    Most services interact with the ``inference`` layer directly,
    but this protocol allows adapters to expose cloud or GPU engines.
    """

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text given a prompt."""


class PersonaPort(ABC):
    """CRUD operations for persona data.

    Persisted storage may be filesystem, database, or remote service.
    """

    @abstractmethod
    async def load_persona(self, name: str) -> Persona:
        """Return persona model by name."""

    @abstractmethod
    async def save_persona(self, persona: Persona) -> None:
        """Persist persona model."""


__all__ = [
    "KernelPort",
    "MemoryPort",
    "InferencePort",
    "PersonaPort",
]
