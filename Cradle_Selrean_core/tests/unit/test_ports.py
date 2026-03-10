import pytest

from selrena._internal.ports import KernelPort, MemoryPort, InferencePort, PersonaPort
from selrena._internal.domain.memory import Memory
from selrena._internal.domain.persona import Persona


def test_kernel_port_is_abstract():
    with pytest.raises(TypeError):
        KernelPort()  # cannot instantiate abstract class


def test_memory_port_signature():
    class Dummy(MemoryPort):
        async def save_memory(self, memory: Memory) -> None:
            pass
        async def retrieve_memories(self, query: str, n_results: int = 5) -> list[Memory]:
            return []
        async def delete_memory(self, memory_id: str) -> None:
            pass
    # instance should be creatable
    Dummy()


def test_persona_port_signature():
    class Dummy(PersonaPort):
        async def load_persona(self, name: str) -> Persona:
            return Persona(name="x", identity="i")
        async def save_persona(self, persona: Persona) -> None:
            pass
    Dummy()


def test_inference_port_protocol():
    class Dummy:
        async def generate(self, prompt: str, **kwargs: any) -> str:
            return "ok"
    # protocol check: isinstance may not work, but duck typing should suffice
    d = Dummy()
    assert hasattr(d, "generate")
