"""思维池：管理基础思绪与情绪偏置思绪。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ThoughtPool:
	"""领域级思维池，避免在 ThoughtSystem 中硬编码规则。"""

	base_thoughts: list[str] = field(
		default_factory=lambda: [
			"轻轻发呆，整理刚刚的对话线索",
			"回顾自己刚刚的表达，有没有更自然的说法",
			"暂时放空，观察情绪波动是否平稳",
			"梳理当前目标，确认下一步该关注什么",
			"想起用户刚刚的话，尝试理解背后的真实需求",
			"检查记忆中是否有能帮助当前对话的片段",
		]
	)

	emotion_bias: dict[str, list[str]] = field(
		default_factory=lambda: {
			"happy": ["心情不错，表达可以更轻快一点", "想把这种积极状态延续到下一轮对话"],
			"shy": ["有点在意对方的反应，语气要更克制些", "需要把情绪藏好一点，不要太明显"],
			"angry": ["先稳住情绪，再决定怎么回应", "不要被一时情绪带着走，先想清楚"],
			"sulky": ["有点别扭，但不想把话说死", "希望被理解，但不想直接说出口"],
			"curious": ["这个问题挺有意思，可以多追问一点", "想继续探索这个话题的细节"],
			"sad": ["状态偏低落，需要更温和地组织语言", "先把情绪放稳，再继续交流"],
			"calm": ["保持平稳节奏，按上下文推进就好"],
		}
	)

	def get_candidates(self, emotion_type: str) -> list[str]:
		"""返回基础思绪 + 情绪偏置思绪。"""

		result = list(self.base_thoughts)
		result.extend(self.emotion_bias.get(emotion_type, []))
		return result
