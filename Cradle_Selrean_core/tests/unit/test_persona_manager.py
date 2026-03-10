import os
import sys

# ensure src on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

from selrena._internal.domain.persona import Persona
from selrena._internal.domain.persona_manager import PersonaManager


def test_persona_manager_includes_time():
    p = Persona(
        name="TestBot",
        identity="我是测试机器人",
        values=["诚实"],
        behavior_patterns=["不撒谎"],
        expression_style={"tone": "友好"},
    )
    mgr = PersonaManager(p)
    prompt = mgr.build_system_prompt()
    assert "TestBot" in prompt
    # timestamp block should be present and roughly current
    import re
    from datetime import datetime
    m = re.search(r"\[Current Time\]\n(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", prompt)
    assert m, "timestamp block missing"
    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    diff = datetime.now() - ts
    assert abs(diff.total_seconds()) < 5, "timestamp not current"
