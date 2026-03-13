
import asyncio
from cradle.selrena.vessel.perception.vision.visual_cortex import VisualCortex
from cradle.schemas.configs.soul import SoulConfig

async def test_visual_cortex():
    vc = VisualCortex(SoulConfig())
    text = "【视觉输入】http://example.com/image.jpg"
    has_sig = vc.has_signal(text)
    print(f"Has signal: {has_sig}")
    
    assert has_sig, "Should detect visual signal"

if __name__ == "__main__":
    asyncio.run(test_visual_cortex())
