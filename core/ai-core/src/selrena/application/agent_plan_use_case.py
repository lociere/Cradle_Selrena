"""
agent_plan_use_case.py - LLM 驱动的智能工具规划用例
"""
import asyncio
import json
from dataclasses import dataclass, field
from typing import List

from .base_use_case import BaseUseCase
from selrena.identity.self_entity import SelrenaSelfEntity
from selrena.llm_engine.llm_engine import LLMEngine, LLMMessage, LLMRequest
from selrena.core.observability.logger import get_logger

logger = get_logger("agent_plan_use_case")

_PLAN_SYSTEM_PROMPT = (
    "你是一个 AI 任务规划助手。根据用户目标和可用工具列表，输出结构化工具调用规划。\n\n"
    "规则：\n"
    "1. 仅从可用工具列表中选择工具名，不要凭空创造\n"
    "2. 每条建议包含 tool_name、purpose、confidence(0~1)、arguments_hint(dict)\n"
    "3. 建议数量 1-4 条，按执行优先级排序\n"
    "4. 无合适工具时输出空 suggestions 列表\n"
    '5. 必须输出合法 JSON，格式：'
    '{"reasoning":"...","plan_summary":"...","suggestions":'
    '[{"tool_name":"...","purpose":"...","confidence":0.9,"arguments_hint":{}}]}'
)


@dataclass
class MCPToolSuggestion:
    tool_name: str
    purpose: str
    confidence: float
    arguments_hint: dict = field(default_factory=dict)


@dataclass
class AgentPlanInput:
    user_goal: str
    scene_id: str = ""
    available_tools: List[dict] = field(default_factory=list)
    trace_id: str = ""


@dataclass
class AgentPlanOutput:
    summary: str
    reasoning: str
    suggestions: List[MCPToolSuggestion]
    trace_id: str


@dataclass
class AgentPlanUseCase(BaseUseCase[AgentPlanInput, AgentPlanOutput]):
    """Agent 规划用例：LLM 驱动的智能工具规划，执行由 TS 层 / MCP 调度完成。"""

    lifecycle_log_level = "debug"
    self_entity: SelrenaSelfEntity
    llm_engine: LLMEngine

    async def _execute(self, input_data: AgentPlanInput, trace_id: str) -> AgentPlanOutput:
        goal = input_data.user_goal.strip()

        if input_data.available_tools:
            tools_lines = []
            for t in input_data.available_tools:
                line = "- " + t.get("name", "?") + " : " + t.get("description", "无描述")
                if t.get("parameters"):
                    line += "（参数：" + ", ".join(t["parameters"]) + "）"
                tools_lines.append(line)
            tools_text = "\n".join(tools_lines)
        else:
            tools_text = "（当前无已注册的 MCP 工具）"

        user_prompt = (
            "【用户目标】\n" + goal
            + "\n\n【可用工具】\n" + tools_text
            + "\n\n请输出规划 JSON。"
        )

        llm_request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=_PLAN_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            provider_key=None,
        )

        suggestions: List[MCPToolSuggestion] = []
        reasoning = ""
        summary = ""

        try:
            raw = await asyncio.to_thread(self.llm_engine.generate, llm_request)
            text = raw.strip()
            fence = chr(96) * 3  # ```
            if fence + "json" in text:
                text = text.split(fence + "json", 1)[1].split(fence, 1)[0].strip()
            elif fence in text:
                text = text.split(fence, 1)[1].split(fence, 1)[0].strip()

            parsed = json.loads(text)
            reasoning = parsed.get("reasoning", "")
            summary = parsed.get("plan_summary", "")
            for item in parsed.get("suggestions", []):
                suggestions.append(MCPToolSuggestion(
                    tool_name=item.get("tool_name", "unknown"),
                    purpose=item.get("purpose", ""),
                    confidence=float(item.get("confidence", 0.5)),
                    arguments_hint=item.get("arguments_hint", {}),
                ))
            logger.debug("LLM 规划成功", goal_len=len(goal), suggestion_count=len(suggestions))

        except Exception as exc:
            logger.warning("LLM 规划失败，返回空建议", error=str(exc), goal=goal[:60])
            reasoning = "LLM 规划异常：" + str(exc)
            summary = "规划失败，请检查 LLM 服务。"

        if not summary:
            summary = "已为目标生成 " + str(len(suggestions)) + " 条工具建议。"

        return AgentPlanOutput(
            summary=summary,
            reasoning=reasoning,
            suggestions=suggestions,
            trace_id=trace_id,
        )
