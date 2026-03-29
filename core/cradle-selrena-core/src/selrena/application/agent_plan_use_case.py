"""
文件名称：agent_plan_use_case.py
所属层级：应用层
核心作用：对外部任务请求进行规划，生成 MCP 工具建议，不直接执行。
"""
from dataclasses import dataclass, field
from typing import List

from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity


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
    trace_id: str = ""


@dataclass
class AgentPlanOutput:
    summary: str
    reasoning: str
    suggestions: List[MCPToolSuggestion]
    trace_id: str


@dataclass
class AgentPlanUseCase(BaseUseCase[AgentPlanInput, AgentPlanOutput]):
    """Agent 规划用例：只做思考与规划，执行由 TS 层 / MCP 调度完成。"""

    lifecycle_log_level = "debug"
    self_entity: SelrenaSelfEntity

    async def _execute(self, input_data: AgentPlanInput, trace_id: str) -> AgentPlanOutput:
        goal = input_data.user_goal.strip()
        lowered = goal.lower()

        suggestions: List[MCPToolSuggestion] = []

        if any(k in goal for k in ["文件", "代码", "项目", "配置"]) or any(k in lowered for k in ["file", "code", "repo"]):
            suggestions.append(
                MCPToolSuggestion(
                    tool_name="workspace.search",
                    purpose="先定位相关文件与符号，再决定改动路径",
                    confidence=0.86,
                    arguments_hint={"query": goal[:60]},
                )
            )
            suggestions.append(
                MCPToolSuggestion(
                    tool_name="workspace.read",
                    purpose="读取上下文并确认约束后生成修改方案",
                    confidence=0.82,
                    arguments_hint={"focus": "target files"},
                )
            )

        if any(k in goal for k in ["运行", "启动", "测试", "构建"]) or any(k in lowered for k in ["run", "test", "build", "start"]):
            suggestions.append(
                MCPToolSuggestion(
                    tool_name="terminal.exec",
                    purpose="执行构建/测试命令并采集输出",
                    confidence=0.8,
                    arguments_hint={"safe": True},
                )
            )

        if any(k in goal for k in ["网页", "文档", "官网", "参考"]) or any(k in lowered for k in ["web", "docs", "reference"]):
            suggestions.append(
                MCPToolSuggestion(
                    tool_name="web.fetch",
                    purpose="检索外部资料以补全规划依据",
                    confidence=0.74,
                    arguments_hint={"keywords": goal[:40]},
                )
            )

        if not suggestions:
            suggestions.append(
                MCPToolSuggestion(
                    tool_name="workspace.search",
                    purpose="先检索仓库上下文，再细化执行计划",
                    confidence=0.65,
                    arguments_hint={"query": goal[:50]},
                )
            )

        summary = f"已为目标生成 {len(suggestions)} 条 MCP 规划建议。"
        reasoning = (
            "该规划仅输出工具建议，不直接执行。"
            "由 TS 层 Agent 调度器根据建议选择 MCP 工具并回传执行结果。"
        )

        return AgentPlanOutput(
            summary=summary,
            reasoning=reasoning,
            suggestions=suggestions,
            trace_id=trace_id,
        )
