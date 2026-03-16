"""
文件名称：chat_use_case.py
所属层级：应用层
核心作用：对话交互全流程编排，纯流程逻辑，不碰任何业务规则
设计原则：
1. 仅做流程编排，所有业务规则全部调用领域层实现
2. 完全不碰场景规则，仅接收内核传入的标准化参数
3. 严格遵循分层边界，不直接调用底层基础设施
4. 所有输出必须经过人设边界校验
"""
from dataclasses import dataclass
from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine
from selrena.core.exceptions import PersonaViolationException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("chat_use_case")


# ======================================
# 用例输入/输出模型
# ======================================
@dataclass
class ChatInput:
    """
    对话用例输入，由TS内核传入的标准化参数
    【核心规范】：完全屏蔽平台/场景细节，AI层看不到任何场景信息
    """
    # 用户输入的纯文本内容（多模态已被内核预处理为语义文本）
    user_input: str
    # 场景唯一ID（仅用于隔离短期记忆，AI层不处理场景规则）
    scene_id: str
    # 对话对象熟悉度 0-10（10=核心用户，0=陌生人，内核已计算完成）
    familiarity: int = 0
    # 全链路追踪ID
    trace_id: str = ""


@dataclass
class ChatOutput:
    """对话用例输出，返回给TS内核的标准化结果"""
    # 生成的回复内容
    reply_content: str
    # 当前情绪状态
    emotion_state: dict
    # 全链路追踪ID
    trace_id: str


# ======================================
# 对话用例核心实现
# ======================================
@dataclass
class ChatUseCase(BaseUseCase[ChatInput, ChatOutput]):
    """
    对话交互全流程用例
    核心作用：编排对话全流程，不碰任何业务规则
    真人逻辑对齐：对应人脑「接收信息→情绪变化→回忆相关记忆→组织语言→输出」的完整思考流程
    """
    # 依赖注入：全局自我实体
    self_entity: SelrenaSelfEntity
    # 依赖注入：LLM推理引擎
    llm_engine: LLMEngine

    async def _execute(self, input_data: ChatInput, trace_id: str) -> ChatOutput:
        """
        对话全流程编排，严格按真人思考逻辑执行
        【规范】：所有业务规则都调用领域层实现，这里仅做流程串联
        """
        logger.debug(
            "对话用例开始执行",
            trace_id=trace_id,
            scene_id=input_data.scene_id,
            familiarity=input_data.familiarity
        )

        # ======================================
        # 步骤1：情绪更新（基于用户输入）
        # ======================================
        self.self_entity.emotion_system.update_by_input(input_data.user_input)
        current_emotion = self.self_entity.emotion_system.get_state()
        logger.debug("情绪更新完成", trace_id=trace_id, emotion=current_emotion)

        # ======================================
        # 步骤2：获取当前场景的短期记忆（上下文）
        # ======================================
        short_term_memory = self.self_entity.get_short_term_memory(input_data.scene_id)
        context_text = short_term_memory.get_context_text(limit=10)
        logger.debug("短期上下文获取完成", trace_id=trace_id, context_length=len(context_text))

        # ======================================
        # 步骤3：检索相关长期记忆
        # ======================================
        relevant_memories = self.self_entity.long_term_memory.retrieve_relevant(
            query=input_data.user_input,
            limit=self.self_entity.inference_config.memory.max_recall_count
        )
        memory_text = "\n".join([f"记忆：{mem.content}" for mem in relevant_memories])
        logger.debug("长期记忆检索完成", trace_id=trace_id, memory_count=len(relevant_memories))

        # ======================================
        # 步骤4：检索相关通用知识库
        # ======================================
        relevant_knowledge = self.self_entity.knowledge_base.retrieve_general_knowledge(
            query=input_data.user_input,
            limit=3
        )
        knowledge_text = "\n".join([f"知识：{entry.content}" for entry in relevant_knowledge])
        logger.debug("通用知识库检索完成", trace_id=trace_id, knowledge_count=len(relevant_knowledge))

        # ======================================
        # 步骤5：构建人设prompt
        # ======================================
        persona_prompt = self.self_entity.persona_injector.build_persona_prompt(
            emotion_state=current_emotion
        )
        logger.debug("人设prompt构建完成", trace_id=trace_id)

        # ======================================
        # 步骤6：拼接完整prompt
        # ======================================
        full_prompt = f"""
{persona_prompt}

===== 相关记忆 =====
{memory_text if memory_text else "无相关记忆"}

===== 相关知识 =====
{knowledge_text if knowledge_text else "无相关知识"}

===== 对话上下文 =====
{context_text}

===== 用户对你说 =====
{input_data.user_input}

请用符合你人设的语气回复：
"""

        # ======================================
        # 步骤7：LLM生成回复
        # ======================================
        raw_reply = self.llm_engine.generate(full_prompt)
        logger.debug("LLM回复生成完成", trace_id=trace_id, reply_length=len(raw_reply))

        # ======================================
        # 步骤8：人设边界红线校验
        # ======================================
        if not self.self_entity.validate_boundary(raw_reply):
            raise PersonaViolationException("生成内容突破人设边界红线，已拦截")
        logger.debug("人设边界校验通过", trace_id=trace_id)

        # ======================================
        # 步骤9：沉淀短期记忆
        # ======================================
        # 新增用户输入到短期记忆
        short_term_memory.add(
            role="user",
            content=input_data.user_input,
            importance=0.7 if input_data.familiarity >= 8 else 0.5
        )
        # 新增生成的回复到短期记忆
        short_term_memory.add(
            role="selrena",
            content=raw_reply,
            importance=0.6
        )
        logger.debug("短期记忆沉淀完成", trace_id=trace_id)

        # ======================================
        # 步骤10：返回标准化结果
        # ======================================
        return ChatOutput(
            reply_content=raw_reply,
            emotion_state=current_emotion,
            trace_id=trace_id
        )