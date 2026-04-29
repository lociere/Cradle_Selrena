"""
文件名称：agent_synthesis_use_case.py
所属层级：应用层
核心作用：接收 TS 层 MCP 工具执行结果，通过 LLM 合成自然语言回复，完成 Agent 闭环。
Pipeline：
  TS 发起 Agent Plan → MCP 执行工具 → TS 回传结果 → AgentSynthesisUseCase → 自然语言回复
"""
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, List

from .base_use_case import BaseUseCase
from selrena.identity.self_entity import SelrenaSelfEntity
from selrena.llm_engine.llm_engine import LLMEngine, LLMMessage, LLMRequest
from selrena.core.observability.logger import get_logger

logger = get_logger("agent_synthesis_use_case")

_SYNTHESIS_SYSTEM_PROMPT = """\
你是 {nickname}。刚才你提出了一个工具调用规划，以下是各工具的执行结果。
请根据结果，以你的人格和说话风格给出最终回复。

要求：
- 直接回复用户的原始目标，不要重复工具名或技术细节
- 如果工具出错，坦然告知，不要假装成功
- 回复开头必须带一个情绪标签：[平静] [开心] [思考] [无奈] 等
- 句末不加句号，风格克制简洁
"""


@dataclass
class AgentSynthesisInput:
    original_goal: str
    scene_id: str = ""
    tool_results: List[dict] = field(default_factory=list)
    trace_id: str = ""


@dataclass
class AgentSynthesisOutput:
    reply_content: str
    emotion_state: dict
    trace_id: str


@dataclass
class AgentSynthesisUseCase(BaseUseCase[AgentSynthesisInput, AgentSynthesisOutput]):
    """Agent 合成用例：LLM 将工具执行结果转化为角色自然语言回复。"""

    lifecycle_log_level = "debug"
    self_entity: SelrenaSelfEntity
    llm_engine: LLMEngine

    async def _execute(self, input_data: AgentSynthesisInput, trace_id: str) -> AgentSynthesisOutput:
        nickname = self.self_entity.persona_config.base.nickname

        # 格式化工具结果
        results_text = self._format_tool_results(input_data.tool_results)

        system_prompt = _SYNTHESIS_SYSTEM_PROMPT.format(nickname=nickname)
        user_prompt = (
            f"【用户目标】\n{input_data.original_goal}\n\n"
            f"【工具执行结果】\n{results_text}\n\n"
            "请给出你的最终回复。"
        )

        llm_request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            provider_key=None,
        )

        reply_content = ""
        emotion_state: dict[str, Any] = {"name": "平静", "intensity": 0.5}

        try:
            # generate() 是同步方法，用 to_thread 避免阻塞事件循环
            reply_content = await asyncio.to_thread(self.llm_engine.generate, llm_request)
            reply_content = reply_content.strip()
            logger.debug("工具结果合成成功", goal_len=len(input_data.original_goal))
        except Exception as exc:
            logger.warning("合成失败，返回兜底回复", error=str(exc))
            reply_content = "[无奈] 工具执行完了，但我整理结果时出了问题——稍后再试吧"

        return AgentSynthesisOutput(
            reply_content=reply_content,
            emotion_state=emotion_state,
            trace_id=trace_id,
        )

    @staticmethod
    def _format_tool_results(results: List[dict]) -> str:
        if not results:
            return "（无工具执行结果）"
        lines = []
        for r in results:
            name = r.get("tool_name", "unknown")
            status = r.get("status", "unknown")
            raw = r.get("result_json", "{}")
            try:
                parsed = json.loads(raw)
                content = json.dumps(parsed, ensure_ascii=False, indent=None)
            except Exception:
                content = raw[:200]
            lines.append(f"- [{status}] {name}: {content}")
        return "\n".join(lines)
