"""
memory_consolidator.py — 异步记忆固化引擎
═════════════════════════════════════════════
所属层级：领域层-记忆模块
核心作用：模拟生物睡眠的「短转长」机制，保持工作记忆的极高信噪比

v4.5 Phase 4: Async Memory Consolidation Engine

流程：
1. 接收固化事件（由 TS 生命时钟空闲触发器发送）
2. 调用 LLM 对指定场景的工作记忆进行摘要提炼
3. 提取核心事实 (Facts) 与用户画像更新
4. 由 EmbeddingEngine 转化为向量
5. 写入 LongTermMemory
6. 清理已总结的 ShortTermMemory

设计原则：
1. 异步后台任务，不阻塞主对话链路
2. 使用专用的摘要提炼 Prompt
3. 通过 DomainEvent 通知外部固化完成
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from selrena.core.event_bus import DomainEvent, DomainEventBus
from selrena.core.observability.logger import get_logger
from selrena.memory_pipeline.long_term_memory import (
    LongTermMemory,
    LongTermMemoryFragment,
    LongTermMemoryType,
)
from selrena.memory_pipeline.short_term_memory import ShortTermMemory
from selrena.llm_engine.embedding_engine import EmbeddingEngine
from selrena.llm_engine.llm_engine import LLMEngine, LLMMessage, LLMRequest

logger = get_logger("memory_consolidator")

# ── 摘要提炼 Prompt ──────────────────────────────────────
_CONSOLIDATION_SYSTEM_PROMPT = """你是一个记忆整理专家。你的任务是从一段对话记录中提取关键信息。

请从以下对话片段中提取：
1. **核心事实**：用户提到的重要事实、偏好、习惯（每条一行，前缀 [FACT]）
2. **情景记忆**：值得长期记住的有意义交互片段（每条一行，前缀 [EPISODE]）
3. **用户偏好**：用户明确或暗示的喜好/厌恶（每条一行，前缀 [PREFERENCE]）

规则：
- 每条提取不超过 50 字
- 只提取有长期价值的信息，日常寒暄忽略
- 如果对话中没有值得提取的内容，只输出 [EMPTY]
- 不要添加任何前言或总结"""


@dataclass
class MemoryConsolidationCompleteEvent(DomainEvent):
    """记忆固化完成事件。"""
    scene_id: str = ""
    consolidated_count: int = 0
    reason: str = ""


class MemoryConsolidator:
    """
    记忆固化引擎。

    接收固化指令后，对指定场景的短期记忆执行 LLM 摘要提炼，
    将结果写入长期记忆，并清理已消化的短期记忆。
    """

    def __init__(
        self,
        llm_engine: LLMEngine,
        long_term_memory: LongTermMemory,
        embedding_engine: EmbeddingEngine | None = None,
    ) -> None:
        self._llm_engine = llm_engine
        self._long_term_memory = long_term_memory
        self._embedding_engine = embedding_engine
        self._event_bus = DomainEventBus()
        self._running_tasks: dict[str, asyncio.Task] = {}
        logger.info("记忆固化引擎初始化完成")

    async def consolidate(
        self,
        scene_id: str,
        short_term_memory: ShortTermMemory,
        reason: str = "idle_timeout",
    ) -> int:
        """
        对指定场景执行记忆固化。

        Parameters
        ----------
        scene_id : str
            场景 ID
        short_term_memory : ShortTermMemory
            该场景的短期记忆实例
        reason : str
            触发原因

        Returns
        -------
        int
            成功固化的记忆条数
        """
        # 防止同一场景并发固化
        if scene_id in self._running_tasks and not self._running_tasks[scene_id].done():
            logger.debug("场景固化任务已在运行，跳过", scene_id=scene_id)
            return 0

        task = asyncio.create_task(self._do_consolidate(scene_id, short_term_memory, reason))
        self._running_tasks[scene_id] = task
        return await task

    async def _do_consolidate(
        self,
        scene_id: str,
        short_term_memory: ShortTermMemory,
        reason: str,
    ) -> int:
        """实际固化逻辑。"""
        fragments = short_term_memory.get_context(limit=50)
        if len(fragments) < 3:
            logger.debug("短期记忆不足，跳过固化", scene_id=scene_id, count=len(fragments))
            return 0

        # 构建对话文本
        conversation_text = "\n".join(f.get_full_content() for f in fragments)
        logger.info(
            "开始记忆固化",
            scene_id=scene_id,
            fragment_count=len(fragments),
            reason=reason,
        )

        # 调用 LLM 提取核心信息
        try:
            extraction_result = await asyncio.to_thread(
                self._llm_engine.generate,
                LLMRequest(
                    messages=[
                        LLMMessage(role="system", content=_CONSOLIDATION_SYSTEM_PROMPT),
                        LLMMessage(role="user", content=conversation_text),
                    ]
                ),
            )
        except Exception as exc:
            logger.error("记忆固化 LLM 调用失败", scene_id=scene_id, error=str(exc), exc_info=True)
            return 0

        # 解析提取结果
        consolidated_count = 0
        if "[EMPTY]" in extraction_result:
            logger.info("固化结果为空，短期记忆无长期价值", scene_id=scene_id)
        else:
            consolidated_count = self._parse_and_store(extraction_result, scene_id)

        # 清理已固化的短期记忆
        if consolidated_count > 0:
            short_term_memory.clear()
            logger.info(
                "记忆固化完成，短期记忆已清理",
                scene_id=scene_id,
                consolidated_count=consolidated_count,
            )

        # 发布固化完成事件
        await self._event_bus.publish(
            MemoryConsolidationCompleteEvent(
                scene_id=scene_id,
                consolidated_count=consolidated_count,
                reason=reason,
            )
        )

        return consolidated_count

    def _parse_and_store(self, extraction_text: str, scene_id: str) -> int:
        """解析 LLM 提取结果并写入长期记忆。"""
        count = 0
        type_map = {
            "[FACT]": LongTermMemoryType.FACT,
            "[EPISODE]": LongTermMemoryType.EPISODIC,
            "[PREFERENCE]": LongTermMemoryType.PREFERENCE,
        }

        for line in extraction_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            memory_type: LongTermMemoryType | None = None
            content = line
            for prefix, mt in type_map.items():
                if line.startswith(prefix):
                    memory_type = mt
                    content = line[len(prefix):].strip()
                    break

            if memory_type is None or not content:
                continue

            fragment = LongTermMemoryFragment(
                content=content,
                memory_type=memory_type,
                weight=0.9,
                tags=["consolidated"],
                scene_id=scene_id,
            )
            self._long_term_memory.add(fragment)
            count += 1
            logger.debug(
                "固化记忆已写入",
                memory_type=memory_type.value,
                content=content[:30],
            )

        return count
