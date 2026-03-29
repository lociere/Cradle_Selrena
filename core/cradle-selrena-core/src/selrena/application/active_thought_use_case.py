"""
文件名称：active_thought_use_case.py
所属层级：应用层
核心作用：主动思维流执行用例，由TS内核的生命时钟驱动，实现「活着」的核心特性
设计原则：
1. 仅做流程编排，不碰业务规则
2. 完全由内核驱动，无需用户触发
3. 不碰任何场景规则，仅做纯思维生成
"""
from dataclasses import dataclass
from typing import ClassVar
from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("active_thought_use_case")


# ======================================
# 用例输入/输出模型
# ======================================
@dataclass
class ActiveThoughtInput:
    """主动思维用例输入，由内核生命时钟触发"""
    # 全链路追踪ID
    trace_id: str = ""
    # 注意力模式：standby/ambient/focused
    attention_mode: str = "ambient"


@dataclass
class ActiveThoughtOutput:
    """主动思维用例输出，返回给内核同步状态"""
    # 生成的内心活动内容
    thought_content: str
    # 当前情绪状态
    emotion_state: dict
    # 全链路追踪ID
    trace_id: str


# ======================================
# 主动思维流用例核心实现
# ======================================
@dataclass
class ActiveThoughtUseCase(BaseUseCase[ActiveThoughtInput, ActiveThoughtOutput]):
    """
    主动思维流执行用例
    核心作用：让月见在没有用户说话时，也有自己的内心活动，实现「活着」的核心特性
    真人逻辑对齐：对应人脑的走神、发呆、内心独白，不需要外界触发
    """
    # 依赖注入：全局自我实体
    lifecycle_log_level: ClassVar[str] = "debug"
    self_entity: SelrenaSelfEntity

    async def _execute(self, input_data: ActiveThoughtInput, trace_id: str) -> ActiveThoughtOutput:
        """主动思维全流程编排"""
        logger.debug(
            "主动思维用例开始执行",
            trace_id=trace_id
        )

        # ======================================
        # 步骤1：情绪自然衰减
        # ======================================
        self.self_entity.emotion_system.decay()
        current_emotion = self.self_entity.emotion_system.get_state()
        logger.debug("情绪自然衰减完成", trace_id=trace_id, emotion=current_emotion)

        # 仅在配置允许的注意力模式下生成主动思维
        active_modes = set(getattr(self.self_entity.inference_config.life_clock, "active_thought_modes", ["ambient", "focused"]))
        if input_data.attention_mode not in active_modes:
            logger.debug(
                "当前注意力模式不生成主动思维，跳过",
                trace_id=trace_id,
                attention_mode=input_data.attention_mode,
                active_modes=list(active_modes),
            )
            return ActiveThoughtOutput(
                thought_content="",
                emotion_state=current_emotion,
                trace_id=trace_id
            )

        # ======================================
        # 步骤2：生成主动思维
        # ======================================
        thought_content = self.self_entity.thought_system.generate_thought()
        logger.debug("主动思维生成完成", trace_id=trace_id, thought=thought_content)

        # ======================================
        # 步骤3：返回标准化结果
        # ======================================
        return ActiveThoughtOutput(
            thought_content=thought_content,
            emotion_state=current_emotion,
            trace_id=trace_id
        )