# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""工具函数的集中导出（迁移阶段）。

旧的工具层（如 logger、异步工具、异常）已移除；使用者应
直接从 core 或各子包导入。

本包本质上重新导出真正的实用模块。
"""

# 将各类工具按类别重新导出以便使用

from .data.dicts import (
    set_by_path,
    get_by_path,
    has_path,
    merge_dicts,
    fill_defaults,
)

from .system.env import (
    IS_PRODUCTION,
    IS_DEBUG,
    IS_WINDOWS,
    IS_LINUX,
    IS_MACOS,
    env_bool,
    env_int,
    env_float,
    env_str,
    env_list,
)

from .events.event_payload import (
    deep_find_first,
    deep_find_first_by_keys,
    extract_fields,
    resolve_event_fields,
)

from .events.event_bus import subscribe, publish

from .io.path import (
    ProjectPath,
    get_config_path,
    get_asset_path,
    get_data_path,
    get_log_path,
    get_model_path,
    get_relative_path,
    normalize_path,
)

from .io.yaml_io import read_yaml, write_yaml, upsert_yaml

from .text.preprocessor import MultimodalPreprocessor

from .text.prompt_builder import PromptBuilder

from .text.string import (
    clean_text,
    clean_for_tts,
    clean_asr_transcript,
    clean_for_dialogue,
    extract_emotion_and_clean_text,
    extract_json_from_text,
    truncate_text,
)

# YAML 辅助函数已经在 io 子包中定义（上述已导出）

# 此处的重复导入可以删除？


__all__: list[str] = [
    # data utils
    "set_by_path",
    "get_by_path",
    "has_path",
    "merge_dicts",
    "fill_defaults",
    # system utils
    "IS_PRODUCTION",
    "IS_DEBUG",
    "IS_WINDOWS",
    "IS_LINUX",
    "IS_MACOS",
    "env_bool",
    "env_int",
    "env_float",
    "env_str",
    "env_list",
    # event utils
    "subscribe",
    "publish",
    "deep_find_first",
    "deep_find_first_by_keys",
    "extract_fields",
    "resolve_event_fields",
    # io utils
    "ProjectPath",
    "get_config_path",
    "get_asset_path",
    "get_data_path",
    "get_log_path",
    "get_model_path",
    "get_relative_path",
    "normalize_path",
    "read_yaml",
    "write_yaml",
    "upsert_yaml",
    # text utils
    "clean_text",
    "clean_for_tts",
    "clean_asr_transcript",
    "clean_for_dialogue",
    "extract_emotion_and_clean_text",
    "extract_json_from_text",
    "truncate_text",
    "MultimodalPreprocessor",
    "PromptBuilder",
]
