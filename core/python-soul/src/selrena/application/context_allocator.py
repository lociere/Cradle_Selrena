"""
context_allocator.py — 认知窗口动态水位控制器
═══════════════════════════════════════════════
所属层级：应用层
核心作用：在 LLM 调用前对上下文进行 Zone 化分配与截断，
         防止多路检索和超长对话撑爆 Token 上限，保证核心人设不被稀释。

v4.5 Phase 3: Context Window Dynamic Water Level Controller

水位线分配策略：
  Zone A (绝对锁定 — 30%): 系统人设 + 核心世界观知识
  Zone B (高优先级 — 40%): 短期工作记忆 (ShortTermMemory)
  Zone C (弹性填充 — 30%): 长期记忆 (LongTermMemory) + 偏好

设计原则：
1. 按 Zone 优先级截断：A > B > C，Zone C 超出则丢弃，绝不侵占 A/B
2. 使用简易字符估算 Token（1 token ≈ 2 汉字 / 4 英文字符）
3. 独立组装器，不侵入 chat_use_case 的编排逻辑，仅做 truncation
"""
from __future__ import annotations

from dataclasses import dataclass
from selrena.core.observability.logger import get_logger

logger = get_logger("context_allocator")

# Token 估算：1 token ≈ 2 汉字 / 4 英文字符（保守系数）
_CHARS_PER_TOKEN = 2.5


def _estimate_tokens(text: str) -> int:
    """粗略估算文本 token 数。"""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


@dataclass(frozen=True)
class ZoneBudget:
    """三区水位预算结果。"""
    zone_a_tokens: int  # 人设 + 知识
    zone_b_tokens: int  # 短期记忆
    zone_c_tokens: int  # 长期记忆 + 偏好


@dataclass
class AllocatedContext:
    """经过水位控制后的上下文片段。"""
    system_persona: str          # Zone A: 人设提示词（总是完整保留）
    knowledge_text: str          # Zone A: 世界知识
    short_term_digest: str       # Zone B: 短期记忆
    session_summary: str         # Zone B: 会话摘要（从 Zone B 预算扣除）
    preference_text: str         # Zone C: 偏好记忆
    ltm_text: str                # Zone C: 长期记忆
    multimodal_text: str         # Zone C: 多模态描述（从 Zone C 预算扣除）
    total_estimated_tokens: int  # 总估算 token 数
    was_truncated: bool          # 是否发生了截断


class ContextAllocator:
    """
    认知窗口水位控制器。

    在 ChatUseCase 调用 LLM 前介入，将各路素材按 Zone 优先级截断，
    确保总 token 不超过模型上限的安全水位（预留 response 空间）。
    """

    def __init__(
        self,
        max_context_tokens: int,
        response_reserve_tokens: int = 512,
        zone_a_ratio: float = 0.30,
        zone_b_ratio: float = 0.40,
        zone_c_ratio: float = 0.30,
    ) -> None:
        self._max_context = max_context_tokens
        self._response_reserve = response_reserve_tokens
        self._zone_a_ratio = zone_a_ratio
        self._zone_b_ratio = zone_b_ratio
        self._zone_c_ratio = zone_c_ratio
        logger.info(
            "上下文分配器初始化",
            max_context=max_context_tokens,
            reserve=response_reserve_tokens,
            zones=f"A={zone_a_ratio:.0%} B={zone_b_ratio:.0%} C={zone_c_ratio:.0%}",
        )

    def _compute_budgets(self) -> ZoneBudget:
        """计算三区 token 预算。"""
        usable = self._max_context - self._response_reserve
        return ZoneBudget(
            zone_a_tokens=int(usable * self._zone_a_ratio),
            zone_b_tokens=int(usable * self._zone_b_ratio),
            zone_c_tokens=int(usable * self._zone_c_ratio),
        )

    def allocate(
        self,
        system_persona: str,
        knowledge_text: str,
        short_term_digest: str,
        session_summary: str,
        preference_text: str,
        ltm_text: str,
        multimodal_text: str,
    ) -> AllocatedContext:
        """
        按水位线分配上下文。

        Zone A (锁定): system_persona + knowledge_text
          → persona 完整保留，knowledge 超出部分截断
        Zone B (高优): short_term_digest + session_summary
          → short_term 优先，session_summary 吃剩余
        Zone C (弹性): preference_text + ltm_text + multimodal_text
          → 严格截断，超出直接丢弃
        """
        budgets = self._compute_budgets()
        was_truncated = False

        # ── Zone A: 人设绝对锁定 ──
        persona_tokens = _estimate_tokens(system_persona)
        knowledge_budget = max(0, budgets.zone_a_tokens - persona_tokens)
        truncated_knowledge = self._truncate_to_tokens(knowledge_text, knowledge_budget)
        if len(truncated_knowledge) < len(knowledge_text):
            was_truncated = True

        # Zone A 如果有剩余，让渡给 Zone B
        zone_a_actual = persona_tokens + _estimate_tokens(truncated_knowledge)
        zone_a_surplus = max(0, budgets.zone_a_tokens - zone_a_actual)

        # ── Zone B: 短期记忆 ──
        zone_b_budget = budgets.zone_b_tokens + zone_a_surplus
        stm_tokens = _estimate_tokens(short_term_digest)
        if stm_tokens > zone_b_budget:
            short_term_digest = self._truncate_to_tokens(short_term_digest, zone_b_budget)
            stm_tokens = _estimate_tokens(short_term_digest)
            was_truncated = True
        summary_budget = max(0, zone_b_budget - stm_tokens)
        truncated_summary = self._truncate_to_tokens(session_summary, summary_budget)
        if len(truncated_summary) < len(session_summary):
            was_truncated = True

        # Zone B 剩余让渡给 Zone C
        zone_b_actual = stm_tokens + _estimate_tokens(truncated_summary)
        zone_b_surplus = max(0, zone_b_budget - zone_b_actual)

        # ── Zone C: 弹性填充 ──
        zone_c_budget = budgets.zone_c_tokens + zone_b_surplus
        # 优先级: preference > ltm > multimodal
        pref_truncated = self._truncate_to_tokens(preference_text, zone_c_budget)
        if len(pref_truncated) < len(preference_text):
            was_truncated = True
        zone_c_remaining = max(0, zone_c_budget - _estimate_tokens(pref_truncated))

        ltm_truncated = self._truncate_to_tokens(ltm_text, zone_c_remaining)
        if len(ltm_truncated) < len(ltm_text):
            was_truncated = True
        zone_c_remaining -= _estimate_tokens(ltm_truncated)

        mm_truncated = self._truncate_to_tokens(multimodal_text, max(0, zone_c_remaining))
        if len(mm_truncated) < len(multimodal_text):
            was_truncated = True

        total = (
            persona_tokens
            + _estimate_tokens(truncated_knowledge)
            + _estimate_tokens(short_term_digest)
            + _estimate_tokens(truncated_summary)
            + _estimate_tokens(pref_truncated)
            + _estimate_tokens(ltm_truncated)
            + _estimate_tokens(mm_truncated)
        )

        if was_truncated:
            logger.info(
                "上下文水位截断已触发",
                total_tokens=total,
                budget=self._max_context - self._response_reserve,
                zone_a=f"{zone_a_actual}/{budgets.zone_a_tokens}",
                zone_b=f"{zone_b_actual}/{budgets.zone_b_tokens}",
            )

        return AllocatedContext(
            system_persona=system_persona,
            knowledge_text=truncated_knowledge,
            short_term_digest=short_term_digest,
            session_summary=truncated_summary,
            preference_text=pref_truncated,
            ltm_text=ltm_truncated,
            multimodal_text=mm_truncated,
            total_estimated_tokens=total,
            was_truncated=was_truncated,
        )

    @staticmethod
    def _truncate_to_tokens(text: str, token_budget: int) -> str:
        """按 token 预算截断文本（保留完整行）。"""
        if not text or token_budget <= 0:
            return ""
        estimated = _estimate_tokens(text)
        if estimated <= token_budget:
            return text
        # 按字符比例截断，尝试保留完整行
        char_limit = int(token_budget * _CHARS_PER_TOKEN)
        truncated = text[:char_limit]
        last_newline = truncated.rfind("\n")
        if last_newline > char_limit * 0.5:
            truncated = truncated[:last_newline]
        return truncated.rstrip()
