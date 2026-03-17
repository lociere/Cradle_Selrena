"""
文件名称：config.py
所属层级：基础设施层
核心作用：定义AI层所有配置的Pydantic模型，运行时由TS内核注入后完全冻结
设计原则：
1. 仅定义配置结构，不硬编码任何默认值，所有值由内核从全局configs注入
2. 所有模型用frozen=True冻结，运行时不可篡改，保证人设核心稳定
3. 绝对不读取本地配置文件，所有配置由内核通过IPC注入
4. 100%对齐全局configs的yaml结构
"""
from pydantic import BaseModel, ConfigDict
from typing import Dict, List


# ======================================
# 人设配置模型（月见的灵魂核心，运行时完全冻结）
# ======================================
class PersonaConfig(BaseModel):
    """
    OC人设核心配置，由TS内核从全局configs/oc/persona.yaml注入
    运行时完全冻结，不可修改，保证人设终身稳定
    """
    model_config = ConfigDict(frozen=True)  # 运行时完全冻结，不可篡改

    # 基础身份信息（终身不变）
    class BasePersona(BaseModel):
        name: str                   # 正式名称
        nickname: str               # 昵称
        role: str                   # 角色定位（如：可爱少女）
        apparent_age: str           # 外显年龄段描述
        gender: str                 # 性别
        appearance: str             # 外观描述
        background: str             # 背景描述
        model_config = ConfigDict(frozen=True)

    # 核心人格与叙事驱动
    class PersonaCore(BaseModel):
        personality: str            # 性格总述
        character_core: str         # 核心人格原则
        likes: str                  # 偏好
        model_config = ConfigDict(frozen=True)

    # 对话风格与情绪表达协议
    class DialoguePolicy(BaseModel):
        dialogue_style: str         # 对话风格
        emotion_control: str        # 情绪标签控制协议
        model_config = ConfigDict(frozen=True)

    # 安全与边界规则
    class SafetyPolicy(BaseModel):
        taboos: str                         # 禁忌规则文本（提示词注入）
        forbidden_phrases: List[str]        # 直接禁用短语（输出校验）
        forbidden_regex: List[str]          # 正则禁用规则（输出校验）
        model_config = ConfigDict(frozen=True)

    base: BasePersona
    core: PersonaCore
    dialogue: DialoguePolicy
    safety: SafetyPolicy


# ======================================
# 推理配置模型
# ======================================
class InferenceConfig(BaseModel):
    """
    AI推理配置，由TS内核从全局configs/ai/inference.yaml注入
    运行时冻结，不可修改
    """
    model_config = ConfigDict(frozen=True)

    # 本地模型配置
    class ModelConfig(BaseModel):
        local_model_path: str       # 本地模型路径
        max_tokens: int             # 最大生成token数
        temperature: float          # 温度系数（0-1，越高越随机）
        top_p: float                # 核采样系数
        frequency_penalty: float    # 频率惩罚
        model_config = ConfigDict(frozen=True)

    # 生命时钟配置（由内核驱动，这里仅做参数定义）
    class LifeClockConfig(BaseModel):
        focused_interval_ms: int     # 聚焦模式下心跳间隔（毫秒）
        ambient_interval_ms: int     # 环境模式下心跳间隔（毫秒）
        default_mode: str            # 默认注意力模式：standby/ambient/focused
        focus_duration_ms: int       # 聚焦模式自动回落时长（毫秒）
        summon_keywords: List[str]   # 呼唤关键词（命中后进入聚焦）
        focus_on_any_chat: bool      # 任意聊天是否进入聚焦
        active_thought_modes: List[str]  # 允许主动思维的模式集合
        model_config = ConfigDict(frozen=True)

    # 记忆配置
    class MemoryConfig(BaseModel):
        max_recall_count: int       # 最大记忆召回数量
        retention_days: int         # 记忆保留天数
        model_config = ConfigDict(frozen=True)

    # 多模态推理编排配置
    class MultimodalConfig(BaseModel):
        enabled: bool                                # 是否启用多模态编排
        strategy: str                                # core_direct/specialist_then_core
        max_items: int                               # 每次最多处理的多模态条目数
        core_model: str                              # 核心多模态模型标识
        image_model: str                             # 图像专有模型标识
        video_model: str                             # 视频专有模型标识
        model_config = ConfigDict(frozen=True)

    model: ModelConfig
    life_clock: LifeClockConfig
    memory: MemoryConfig
    multimodal: MultimodalConfig


# ======================================
# 云端/API LLM 配置模型
# ======================================
class LLMConfig(BaseModel):
    """云端LLM或API调用参数配置（如 DeepSeek/OpenAI/Azure）"""

    api_type: str  # deepseek / openai / azure / anthropic / local
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None

    # 可选：自定义请求结构
    request_method: str | None = None  # GET/POST/PUT/PATCH/DELETE
    request_path: str | None = None
    request_headers: dict[str, str] | None = None
    request_body_template: str | None = None

    # 可选：自定义响应提取路径（点分隔）
    response_extract: str | None = None

    model_config = ConfigDict(frozen=True)


# ======================================
# 全局配置根模型
# ======================================
class GlobalAIConfig(BaseModel):
    """AI层全局配置，内核启动时一次性注入，运行时完全冻结
    是AI层所有配置的唯一来源，绝对不读取本地文件
    """
    model_config = ConfigDict(frozen=True)

    persona: PersonaConfig
    inference: InferenceConfig
    llm: LLMConfig | None = None