"""Basic smoke tests for the `selrena` package.

These exercises ensure the core modules import correctly after the final rename.
"""

import os, sys
# ensure src directory is on sys.path so selrena can be imported during tests
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

from selrena.domain import Persona, Memory


def test_persona_creation():
    p = Persona(name="A", identity="id")
    assert p.name == "A" and p.identity == "id"


def test_memory_serialization():
    m = Memory(content="hello")
    data = m.to_dict()
    # ensure content preserved and default fields exist
    assert data["content"] == "hello"
    assert "emotion" in data and "metadata" in data


def test_container_imports():
    # container should import without errors and use Persona from new package
    from selrena.container import AIContainer
    assert hasattr(AIContainer, "initialize")


def test_schemas_import():
    from selrena.schemas import BaseEvent, SpeakAction
    assert "BaseEvent" in BaseEvent.__name__ and "SpeakAction" in SpeakAction.__name__


def test_application_imports():
    from selrena.application import ConversationService, MemoryService, ReasoningService
    # instantiate with minimal mocks
    class Dummy:
        pass
    cs = ConversationService(persona=Dummy(), llm=Dummy(), kernel=Dummy(), memory=Dummy())
    ms = MemoryService(memory_port=Dummy())
    rs = ReasoningService(llm=Dummy())
    assert hasattr(cs, "process_message") and hasattr(ms, "memorize") and hasattr(rs, "reason")


def test_adapters_and_ports_imports():
    from selrena.adapters import KernelAdapter, MemoryAdapter, PersonaAdapter
    from selrena.ports import KernelPort, MemoryPort, Personaport
    # dummy instantiation
    assert KernelAdapter is not None and MemoryAdapter is not None and PersonaAdapter is not None
    assert issubclass(KernelPort, object) and issubclass(MemoryPort, object) and issubclass(Personaport, object)


def test_utils_imports():
    from selrena.utils import logger, clean_text, ProjectPath
    assert hasattr(logger, "info")
    assert clean_text("hello") == "hello"
    assert isinstance(ProjectPath.PROJECT_ROOT, type(ProjectPath.PROJECT_ROOT))


def test_core_imports():
    from selrena.core import AIService, ConfigManager, EventBusClient, AICoreService
    # instantiate minimal objects
    assert AIService is not None
    assert isinstance(ConfigManager(), ConfigManager)
    assert EventBusClient is not None
    assert AICoreService is not None


def test_container_import():
    from selrena.container import AIContainer
    assert hasattr(AIContainer, "initialize")
