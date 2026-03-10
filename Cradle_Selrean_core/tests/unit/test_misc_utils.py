import sys, os
# ensure package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from selrena._internal.utils import MultimodalPreprocessor, PromptBuilder


def test_preprocessor_and_prompt_builder_import():
    assert hasattr(MultimodalPreprocessor, "sanitize_for_text_core")
    assert callable(MultimodalPreprocessor.sanitize_for_text_core)
    assert PromptBuilder.build("a","b") == "a\nb"
