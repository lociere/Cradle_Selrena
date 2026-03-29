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
import asyncio
import re
from dataclasses import dataclass
from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.contracts.kernel_ingress_contracts import PerceptionEventContentModel
from selrena.inference.llm_engine import LLMEngine, LLMMessage, LLMRequest
from selrena.inference.multimodal_router import MultimodalRouter, VisionMessage
from selrena.core.exceptions import PersonaViolationException
from selrena.core.observability.logger import get_logger

# 月见人设全量情绪标签正则（与 persona_injector.py 及 perception-builder.ts 同步维护）
# 覆盖括号格式 [开心]、[emotion:happy] 及无括号前缀 emotion: happy
_EMOTION_LABEL_WORDS = (
    r'平静|开心|疑惑|撒娇|严肃|害羞|生气|委屈|思考'           # persona 明确标签
    r'|高兴|愉快|愤怒|难过|傲娇|好奇|冷静|激动|无奈|担心|兴奋'  # 扩展同义词
    r'|calm|happy|curious|coy|tsundere|shy|angry|aggrieved|thinking'  # 英文别名
    r'|joyful|pleased|furious|sad|peaceful|worried|excited|sulky'
)
# 括号包裹格式（任意位置）：[开心] [emotion:happy] (calm) 《思考》 等
_EMOTION_TAG_RE = re.compile(
    r'[\[\(（【《<]\s*(?:emotion|情绪)?\s*[:：\-]?\s*(?:' + _EMOTION_LABEL_WORDS + r')\s*[\]\)）】》>]',
    re.IGNORECASE,
)
# 无括号前缀格式（仅行首）：emotion: happy 情绪：开心
_EMOTION_PREFIX_RE = re.compile(
    r'^(?:emotion|情绪)\s*[:：]\s*(?:' + _EMOTION_LABEL_WORDS + r')\s*',
    re.IGNORECASE,
)


def _strip_emotion_tags(text: str) -> str:
    """剥除 LLM 输出中的全部情绪标签，供存入记忆前使用。

    处理范围：
      - 括号格式（任意位置）：[开心] [emotion:happy] (shy) 等
      - 无括号前缀（行首）：emotion: happy / 情绪：开心
    """
    value = _EMOTION_TAG_RE.sub('', text).strip()
    value = _EMOTION_PREFIX_RE.sub('', value).strip()
    return re.sub(r' {2,}', ' ', value).strip()


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
    # 统一模型输入
    model_input: PerceptionEventContentModel | dict
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
    # 依赖注入：多模态路由器
    multimodal_router: MultimodalRouter

    def _build_memory_digest(self, input_data: ChatInput, user_text: str, multimodal_text: str) -> tuple[str, str, str, str]:
        memory_query = "\n".join(part for part in [user_text, multimodal_text] if part).strip() or user_text

        preference_memories = self.self_entity.long_term_memory.get_preference_memory()
        preference_text = "\n".join([f"偏好记忆：{mem.content}" for mem in preference_memories])

        relevant_memories = self.self_entity.long_term_memory.retrieve_relevant(
            query=memory_query,
            limit=self.self_entity.inference_config.memory.max_recall_count
        )
        memory_text = "\n".join([f"记忆：{mem.content}" for mem in relevant_memories])

        persona_knowledge = self.self_entity.knowledge_base.get_persona_knowledge()
        persona_knowledge_text = "\n".join([f"人设知识：{entry.content}" for entry in persona_knowledge])

        relevant_knowledge = self.self_entity.knowledge_base.retrieve_general_knowledge(
            query=memory_query,
            limit=None,
        )
        knowledge_text = "\n".join([f"知识：{entry.content}" for entry in relevant_knowledge])

        return preference_text, memory_text, persona_knowledge_text, knowledge_text

    def _build_short_term_digest(self, scene_id: str) -> str:
        short_term_memory = self.self_entity.get_short_term_memory(scene_id)
        memory_config = self.self_entity.inference_config.memory
        important_fragments = short_term_memory.get_important_fragments(threshold=0.65)
        selected_fragments = important_fragments[-memory_config.context_limit:]
        if not selected_fragments:
            selected_fragments = short_term_memory.get_context(limit=memory_config.context_limit)
        return "\n".join([fragment.get_full_content() for fragment in selected_fragments])

    def _build_system_message(
        self,
        persona_prompt: str,
        current_emotion: dict,
        session_summary: str,
        short_term_digest: str,
        preference_text: str,
        memory_text: str,
        persona_knowledge_text: str,
        knowledge_text: str,
        multimodal_text: str,
    ) -> str:
        return f"""
{persona_prompt}

===== 会话机制 =====
你正在一个持续在线的长会话中回复，必须承接历史上下文，不要把每一轮都当成第一次见面。

===== 当前情绪状态 =====
{current_emotion}

===== 历史会话摘要 =====
{session_summary if session_summary else "无历史摘要"}

===== 短期记忆摘录 =====
{short_term_digest if short_term_digest else "无短期记忆摘录"}

===== 长期偏好记忆 =====
{preference_text if preference_text else "无长期偏好记忆"}

===== 相关长期记忆 =====
{memory_text if memory_text else "无相关记忆"}

===== 人设固定知识 =====
{persona_knowledge_text if persona_knowledge_text else "无人设固定知识"}

===== 相关通用知识 =====
{knowledge_text if knowledge_text else "无相关知识"}

===== 用户发送的媒体内容 =====
（以下是对用户发来的图片/表情包/视频的简要描述，请自然地参考这些内容进行回复，不要逐字复述描述词）
{multimodal_text if multimodal_text else "无图片或视频"}
""".strip()

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

        runtime = self.self_entity.get_scene_runtime(input_data.scene_id)
        async with runtime.lock:
            # ======================================
            # 步骤0：统一输入路由（固定策略）
            # multimodal_router.route() 在 specialist_then_core 策略下会同步调用
            # 视觉 API（阻塞 HTTP），必须放入线程池执行，不能直接 await。
            # ======================================
            route_result = await asyncio.to_thread(
                self.multimodal_router.route, input_data.model_input
            )
            user_text = route_result.primary_text or "[多模态输入]"
            multimodal_text = route_result.semantic_text
            if multimodal_text:
                logger.info(
                    "视觉专家描述已生成",
                    strategy=route_result.strategy,
                    semantic_text=multimodal_text,
                )

            # core_direct 策略：将 VisionMessage 列表转为 LLMMessage（vision 格式）
            vision_llm_messages: list[LLMMessage] = [
                LLMMessage(
                    role="user",
                    content=vm.prompt,
                    vision_url=vm.uri,
                    vision_mime=vm.mime_type,
                )
                for vm in route_result.vision_messages
            ]
            # core_direct 时使用多模态专用推理提供商，否则走默认
            vision_provider_key: str | None = (
                self.self_entity.inference_config.multimodal.core_model
                if vision_llm_messages
                else None
            )

            # ======================================
            # 步骤1：情绪更新（基于用户输入）
            # ======================================
            emotion_input = "\n".join(part for part in [user_text, multimodal_text] if part).strip() or user_text
            self.self_entity.emotion_system.update_by_input(emotion_input)
            current_emotion = self.self_entity.emotion_system.get_state()
            logger.debug("情绪更新完成", trace_id=trace_id, emotion=current_emotion)

            # ======================================
            # 步骤2：构建长期记忆 / 知识上下文
            # ======================================
            preference_text, memory_text, persona_knowledge_text, knowledge_text = self._build_memory_digest(
                input_data=input_data,
                user_text=user_text,
                multimodal_text=multimodal_text,
            )
            logger.debug("长期上下文构建完成", trace_id=trace_id)

            # ======================================
            # 步骤3：构建系统消息并写入当前用户轮次
            # ======================================
            persona_prompt = self.self_entity.persona_injector.build_persona_prompt(
                emotion_state=current_emotion
            )
            session = runtime.session
            short_term_memory = runtime.short_term_memory
            user_importance = 0.7 if input_data.familiarity >= 8 else 0.5
            session.append_message(role="user", content=user_text)
            short_term_memory.add(
                role="user",
                content=user_text,
                importance=user_importance,
            )
            session.compact_history(
                trigger_count=self.self_entity.inference_config.memory.summary_trigger_count,
                keep_recent_count=self.self_entity.inference_config.memory.summary_keep_recent_count,
                max_summary_chars=self.self_entity.inference_config.memory.summary_max_chars,
            )
            short_term_digest = self._build_short_term_digest(input_data.scene_id)
            system_message = self._build_system_message(
                persona_prompt=persona_prompt,
                current_emotion=current_emotion,
                session_summary=session.summary_text,
                short_term_digest=short_term_digest,
                preference_text=preference_text,
                memory_text=memory_text,
                persona_knowledge_text=persona_knowledge_text,
                knowledge_text=knowledge_text,
                multimodal_text=multimodal_text,
            )
            llm_request = LLMRequest(
                messages=[
                    LLMMessage(role="system", content=system_message),
                    # core_direct：视觉消息插在系统消息之后、对话历史之前
                    *vision_llm_messages,
                    *[
                        LLMMessage(role=message.role, content=message.content)
                        for message in session.get_recent_messages(
                            limit=self.self_entity.inference_config.memory.conversation_window,
                        )
                    ],
                ]
            )
            logger.debug(
                "消息式会话请求构建完成",
                trace_id=trace_id,
                live_messages=len(llm_request.messages),
                summary_length=len(session.summary_text),
            )

            # ======================================
            # 步骤4：LLM生成回复（线程外执行，避免阻塞事件循环）
            # ======================================
            raw_reply = await asyncio.to_thread(
                self.llm_engine.generate, llm_request, vision_provider_key
            )
            logger.debug("LLM回复生成完成", trace_id=trace_id, reply_length=len(raw_reply))

            # ======================================
            # 步骤5：人设边界红线校验
            # ======================================
            if not self.self_entity.validate_boundary(raw_reply):
                raise PersonaViolationException("生成内容突破人设边界红线，已拦截")
            logger.debug("人设边界校验通过", trace_id=trace_id)

            # ======================================
            # 步骤6：沉淀会话态与短期记忆
            # ======================================
            # 存入记忆前剥除情绪标签，防止污染未来 LLM 上下文
            clean_reply = _strip_emotion_tags(raw_reply)
            session.append_message(role="assistant", content=clean_reply)
            session.compact_history(
                trigger_count=self.self_entity.inference_config.memory.summary_trigger_count,
                keep_recent_count=self.self_entity.inference_config.memory.summary_keep_recent_count,
                max_summary_chars=self.self_entity.inference_config.memory.summary_max_chars,
            )
            short_term_memory.add(
                role="selrena",
                content=clean_reply,
                importance=0.6
            )
            logger.debug("会话态与短期记忆沉淀完成", trace_id=trace_id)

            # ======================================
            # 步骤7：返回标准化结果
            # ======================================
            return ChatOutput(
                reply_content=raw_reply,  # 返回原始回复，由 TS cleanOutboundReply 做最终清洗
                emotion_state=current_emotion,
                trace_id=trace_id
            )