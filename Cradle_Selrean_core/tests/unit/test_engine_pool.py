import pytest
import asyncio
import sys, os

# ensure src package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from selrena._internal.inference.engine_pool import BrainFactory, HybridBrainRouter
from selrena._internal.inference.engine_pool import BaseBrainBackend


def test_engine_pool_router_and_backends():
    async def inner():
        factory = BrainFactory()
        stub = factory.create("dummy")
        assert isinstance(stub, BaseBrainBackend)
        result = await stub.generate("hello world")
        assert "brain:dummy" in result

        router = HybridBrainRouter(factory)
        backend = await router.route(is_visual=False)
        assert isinstance(backend, BaseBrainBackend)
        resp = await backend.generate("testing")
        assert resp
    asyncio.run(inner())


def test_inference_package_exports():
    # Verify that top-level inference package still exports router factory
    # internal routers are imported directly in tests
    from selrena._internal.inference.engine_pool import BrainFactory as BF
    from selrena._internal.inference.engine_pool import HybridBrainRouter as HR

    assert BF is BrainFactory
    assert HR is HybridBrainRouter
