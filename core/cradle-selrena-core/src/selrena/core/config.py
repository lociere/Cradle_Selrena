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
from pydantic import BaseModel
from typing import Dict, List


# ======================================
# 人设配置模型（月见的灵魂核心，运行时完全冻结）
# ======================================
class PersonaConfig(BaseModel):
    """
    OC人设核心配置，由TS内核从全局configs/oc/persona.yaml注入
    运行时完全冻结，不可修改，保证人设终身稳定
    """
    class Config:
        frozen = True  # 运行时完全冻结，不可篡改

    # 基础身份信息（终身不变）
    class BasePersona(BaseModel):
        name: str               # 正式英文名
        nickname: str           # 中文昵称（月见）
        age: int                # 年龄
        gender: str             # 性别
        core_identity: str      # 核心身份定位
        self_description: str   # 自我描述
        class Config: frozen = True

    base: BasePersona
    # 性格特质（key=特质名，value=0-10分，用于人设注入）
    character_traits: Dict[str, int]
    # 行为规则（用于prompt注入）
    behavior_rules: List[str]
    # 边界红线（绝对不可突破，用于输出校验）
    boundary_limits: List[str]


# ======================================
# 推理配置模型
# ======================================
class InferenceConfig(BaseModel):
    """
    AI推理配置，由TS内核从全局configs/ai/inference.yaml注入
    运行时冻结，不可修改
    """
    class Config:
        frozen = True

    # 本地模型配置
    class ModelConfig(BaseModel):
        local_model_path: str       # 本地模型路径
        max_tokens: int             # 最大生成token数
        temperature: float          # 温度系数（0-1，越高越随机）
        top_p: float                # 核采样系数
        frequency_penalty: float    # 频率惩罚
        class Config: frozen = True

    # 生命时钟配置（由内核驱动，这里仅做参数定义）
    class LifeClockConfig(BaseModel):
        thought_interval_ms: int    # 主动思维触发间隔（毫秒）
        class Config: frozen = True

    # 记忆配置
    class MemoryConfig(BaseModel):
        max_recall_count: int       # 最大记忆召回数量
        retention_days: int         # 记忆保留天数
        class Config: frozen = True

    model: ModelConfig
    life_clock: LifeClockConfig
    memory: MemoryConfig


# ======================================
# 全局配置根模型
# ======================================
class GlobalAIConfig(BaseModel):
    """
    AI层全局配置，内核启动时一次性注入，运行时完全冻结
    是AI层所有配置的唯一来源，绝对不读取本地文件
    """
    class Config:
        frozen = True

    persona: PersonaConfig
    inference: InferenceConfig