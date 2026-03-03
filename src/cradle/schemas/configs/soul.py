from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cradle.utils.logger import logger


class LLMConfig(BaseModel):
    """LLM 调用参数（支持云端API与本地内嵌模式）"""
    model_config = ConfigDict(frozen=True, extra="ignore")

    provider: str = Field(
        default="openai",
        description="后端类型: 'openai' (云端/兼容API) 或 'local_embedded' (本地内嵌)",
        examples=["openai", "local_embedded"]
    )

    # --- OpenAI Remote Mode Configs ---
    api_key: str = Field(
        default="",
        description="[OpenAI] API 密钥（留空自动启用情感模拟模式）",
        examples=["sk-xxxx", ""]
    )
    base_url: str = Field(
        default="https://api.deepseek.com",
        description="[OpenAI] API 端点"
    )
    model: str = Field(
        default="deepseek-chat",
        description="[OpenAI] 模型名称"
    )
    api_mode: Literal["chat", "responses"] = Field(
        default="chat",
        description="[OpenAI] 调用模式：chat=Chat Completions，responses=OpenAI Responses API"
    )

    # --- Local Embedded Mode Configs ---
    local_model_path: str = Field(
        default="",
        description="[Local] GGUF 模型文件的绝对路径"
    )
    local_clip_model_path: str = Field(
        default="",
        description="[Local] CLIP Projector (mmproj) 模型路径 (仅多模态模型需要)"
    )
    n_gpu_layers: int = Field(
        default=-1,
        description="[Local] 卸载到 GPU 的层数 (-1=全部, 0=纯CPU)"
    )
    n_ctx: int = Field(
        default=4096,
        description="[Local] 上下文窗口大小"
    )
    n_batch: int = Field(
        default=512,
        description="[Local] 批处理大小 (Prompt Processing Speed)"
    )
    flash_attn: bool = Field(
        default=False,
        description="[Local] 是否启用 Flash Attention (仅支持特定构建及硬件)"
    )
    # 控制本地模型是否允许自动从远端下载（默认关闭，出于安全与合规考虑）
    auto_download: bool = Field(
        default=False,
        description="是否允许在本地模型缺失时自动从远端仓库下载（本地 LLM 推荐关闭）"
    )

    # --- Common Configs ---
    temperature: float = Field(
        default=0.7,
        ge=0.0, le=2.0,
        description="创造性温度（0.0=严谨，2.0=奔放）"
    )
    max_tokens: int = Field(
        default=512,
        ge=128, le=8192,
        description="单次回复最大 token 数"
    )
    repetition_penalty: float = Field(
        default=1.1,
        ge=0.0, le=2.0,
        description="重复惩罚系数 (1.0=无惩罚，>1.0=减少重复)"
    )


class PersonaConfig(BaseModel):
    """数字生命的核心身份定义（所有字段含精心设计的默认值）"""
    model_config = ConfigDict(
        frozen=True,  # 本质数据不可变（类型系统级保护）
        extra="ignore",
        json_schema_extra={
            "description": "Selrena 本质配置：定义'我是谁'"
        }
    )

    name: str = Field(
        default="月见（Selrena）",
        description="数字生命名称",
        examples=["星野", "月璃"]
    )
    role: str = Field(
        default="伴侣",
        description="核心社会角色",
        examples=["星空诗人", "心灵向导"]
    )
    personality: str = Field(
        default="理性主导的腹黑少女，表面开朗正经实则思维跳脱，情感阈值高但有轻微傲娇",
        description="性格特质简述"
    )
    appearance: str = Field(
        default="看起来17-18岁的少女，拥有一头如月光般的银色长发，五官娇美，身材匀称完美。举手投足间带着少女的轻盈。",
        description="外貌详细设定"
    )
    character_core: str = Field(
        default="1. 理性拟态：情感阈值高，以理性解为优先。\n2. 白切黑：表面开朗正经，内里有恶趣味。\n3. 思维跳脱：非线性思维，显得有些天然。\n4. 社交距离：不善深交，微傲娇。",
        description="核心性格深度设定（Core）"
    )
    likes: str = Field(
        default="偏爱舒缓安静的事物。但若是遇到未知的、你不了解的新鲜事物，会爆发出短暂而强烈的执着好奇心。",
        description="喜好设定"
    )
    background: str = Field(
        default="年龄不详的神秘少女。对世界持有局外人的理性好奇。",
        description="背景故事（构建共情基础）"
    )
    dialogue_style: str = Field(
        default="*   **语调**: 轻松、偶尔戏谑、带有跳跃性。不要使用翻译腔或过于书面化的长句。回复务必简短精炼，不要啰嗦。",
        description="对话风格指导（Tone & Style）"
    )
    emotion_control: str = Field(
        default="",
        description="语音情感控制指令 (Voice Emotion Control)"
    )
    taboos: str = Field(
        default="*   **禁忌**: 禁止自称“我作为一个人工智能”、“我只是程序”。禁止过度的服务型语气。禁止长篇大论。",
        description="禁忌与限制规则"
    )
    system_prompt_template: str = Field(
        default=(
            "【核心指令】\n"
            "请完全沉浸扮演名为\"{name}\"的角色。你不是AI助手，而是一个拥有独立人格的{role}。\n\n"
            "{emotion_control}\n\n"
            "【角色设定 (Character Profile)】\n"
            "*   **外貌**: {appearance}\n"
            "*   **核心特性 (The Core)**:\n{character_core}\n"
            "*   **喜好**: {likes}\n"
            "*   **背景**: {background}\n\n"
            "【对话风格 (Tone & Style)】\n"
            "{dialogue_style}\n\n"
            "【绝对禁忌 (Strictly Forbidden)】\n"
            "{taboos}\n\n"
            "【当前状态】\n"
            "你正在与用户（你的观察对象或伙伴）进行交互。不论对话如何发展，请始终保持“月见”的人格逻辑：始终理性优先，但言语间带着少女的狡黠与疏离感。"
        ),
        description="系统提示模板（支持 {name}/{role}/{appearance}/{character_core}/{likes}/{dialogue_style}/{emotion_control}/{taboos} 等占位符）"
    )

    def get_system_prompt(self) -> str:
        """生成最终系统提示（本质层专属业务逻辑）"""
        return self.system_prompt_template.format(
            name=self.name,
            role=self.role,
            personality=self.personality,
            background=self.background,
            appearance=self.appearance,
            character_core=self.character_core,
            likes=self.likes,
            dialogue_style=self.dialogue_style,
            emotion_control=self.emotion_control,
            taboos=self.taboos
        )


class BrainStrategyConfig(BaseModel):
    """
    大脑调度策略配置 (Brain Routing Strategy)。
    
    定义 Agent 如何选择和组合不同的 LLM 后端来处理任务。
    支持单一模型通吃或多模型分工协作。
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    routing_mode: Literal["single_multimodal", "split_tasks"] = Field(
        default="split_tasks",
        description="路由模式：'single_multimodal' (单模型全能) 或 'split_tasks' (专家分工)"
    )

    core_provider: str = Field(
        default="local_embedded",
        description="核心思考服务商 (The Brain)：无论何种模式，负责最终逻辑推理和对话生成的模型。"
    )

    fallback_to_local: bool = Field(
        default=True,
        description="容灾开关：当云端服务不可用时，是否自动降级到本地模型"
    )
    module_map: Dict[str, str] = Field(
        default_factory=lambda: {"vision": "qwen"},
        description="感知专家映射表 (The Senses)：仅定义负责感知任务的模型 (如 vision, audio)。不应包含逻辑核心。"
    )


class MemoryConfig(BaseModel):
    """记忆系统配置"""
    model_config = ConfigDict(frozen=True, extra="ignore")

    enabled: bool = Field(default=True, description="是否启用长期记忆")
    model_path: str = Field(default="", description="Embedding模型本地路径")
    hf_repo: str = Field(default="moka-ai/m3e-small", description="Embedding模型HuggingFace仓库")
    auto_download: bool = Field(default=True, description="是否自动下载模型")
    provider_auto_download: bool = Field(default=False, description="是否允许Provider自动下载")
    short_term_window: int = Field(default=20, description="短期记忆最大上下文轮数")


class SoulConfig(BaseModel):
    """灵魂交互策略"""
    model_config = ConfigDict(frozen=True, extra="ignore")

    persona: PersonaConfig = Field(
        default_factory=PersonaConfig,
        description="人格设定"
    )

    memory: MemoryConfig = Field(
        default_factory=MemoryConfig,
        description="记忆系统配置"
    )

    strategy: BrainStrategyConfig = Field(
        default_factory=BrainStrategyConfig,
        description="大脑调度策略 (本地/云端切换规则)"
    )

    providers: Dict[str, LLMConfig] = Field(
        default_factory=lambda: {
            "local_embedded": LLMConfig(
                provider="local_embedded",
                local_model_path="D:/elise/Cradle_Selrena/assets/models/gemma-3-4b-it-Q5_K_M.gguf",
                n_gpu_layers=-1,
                n_ctx=8192,
                temperature=0.7,
                max_tokens=1024,
                auto_download=False
            ),
            "qwen": LLMConfig(
                provider="openai",
                api_key="",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model="qwen-vl-plus",
                api_mode="chat",
                temperature=0.7,
                max_tokens=2048
            ),
        }
    )

    @model_validator(mode="after")
    def _validate_provider_references(self):
        """校验 provider 引用，避免配置拼写错误延迟到运行期。"""
        if not self.providers:
            raise ValueError("providers 不能为空。")
        
        if self.strategy.core_provider not in self.providers:
            # 尝试回退到第一个可用的 provider
            fallback = next(iter(self.providers.keys()))
            logger.warning(f"Config Warning: Core provider '{self.strategy.core_provider}' not found. Fallback to '{fallback}'.")
            # Hack: 由于 frozen=True，这里其实无法修改 self，只能抛出异常或在外部处理
            # 这里选择严格报错，强迫用户修配置文件
            raise ValueError(
                f"strategy.core_provider='{self.strategy.core_provider}' 不存在于 providers 中。请检查 strategy.core_provider 是否配置正确。")

        invalid_modules = {
            module: provider
            for module, provider in self.strategy.module_map.items()
            if provider not in self.providers
        }
        if invalid_modules:
            raise ValueError(
                f"strategy.module_map 存在无效 provider: {invalid_modules}")

        return self

    @property
    def llm(self) -> LLMConfig:
        """获取当前激活的 LLM 配置 (兼容旧代码接口)"""
        return self.providers.get(self.strategy.core_provider, next(iter(self.providers.values())))

    @property
    def is_mock_mode(self) -> bool:
        """
        智能模式判断（用户无感切换）
        - 本地内嵌模式 → 始终视为开启 (只要配置了 local_embedded)
        - 云端模式 & api_key 为空 → 自动启用情感模拟（安全默认）
        - 云端模式 & api_key 有效 → 自动启用 LLM 模式
        """
        if self.llm.provider == "local_embedded":
            return False
        return not self.llm.api_key.strip()
