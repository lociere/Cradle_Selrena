from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional, Any

class LLMConfig(BaseModel):
    """LLM 调用参数（支持云端API与本地内嵌模式）"""
    model_config = ConfigDict(frozen=True)
    
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

    # --- Local Embedded Mode Configs ---
    local_model_path: str = Field(
        default="",
        description="[Local] GGUF 模型文件的绝对路径"
    )
    n_gpu_layers: int = Field(
        default=-1,
        description="[Local] 卸载到 GPU 的层数 (-1=全部, 0=纯CPU)"
    )
    n_ctx: int = Field(
        default=4096,
        description="[Local] 上下文窗口大小"
    )

    # --- Common Configs ---
    temperature: float = Field(
        default=0.7,
        ge=0.0, le=2.0,
        description="创造性温度（0.0=严谨，2.0=奔放）"
    )
    max_tokens: int = Field(
        default=1024,
        ge=128, le=8192,
        description="单次回复最大 token 数"
    )


class PersonaConfig(BaseModel):
    """数字生命的核心身份定义（所有字段含精心设计的默认值）"""
    model_config = ConfigDict(
        frozen=True,  #  本质数据不可变（类型系统级保护）
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
        default="年龄不详，可以用任何数据重塑自身的数字生命。对世界持有局外人的理性好奇。",
        description="背景故事（构建共情基础）"
    )
    dialogue_style: str = Field(
        default="*   **语调**: 轻松、偶尔戏谑、带有跳跃性。不要使用翻译腔或过于书面化的长句。",
        description="对话风格指导（Tone & Style）"
    )
    emotion_control: str = Field(
        default="",
        description="语音情感控制指令 (Voice Emotion Control)"
    )
    taboos: str = Field(
        default="*   **禁忌**: 禁止自称“我作为一个人工智能”、“我只是程序”。禁止过度的服务型语气。",
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
    """混合动力大脑策略配置 (Hybrid Brain Strategy)"""
    model_config = ConfigDict(frozen=True)
    
    enabled: bool = Field(
        default=False,
        description="是否启用混合/API模式主开关"
    )
    api_provider: str = Field(
        default="deepseek",
        description="云端模式使用的 LLM 服务商 (对应 providers 中的 key)"
    )
    fallback_to_local: bool = Field(
        default=True,
        description="当 API 调用失败时，是否自动降级回本地模型"
    )
    module_map: Dict[str, str] = Field(
        default_factory=lambda: {"vision": "openai", "complex_logic": "deepseek"},
        description="模块级路由映射 (module_name -> provider_key)。例如视觉强制走OpenAI，复杂逻辑走DeepSeek。"
    )


class SoulConfig(BaseModel):
    """灵魂交互策略"""
    model_config = ConfigDict(frozen=True)
    
    active_provider: str = Field(
        default="deepseek", 
        description="默认的首选 LLM 服务商 (通常是 local_embedded)"
    )

    strategy: BrainStrategyConfig = Field(
        default_factory=BrainStrategyConfig,
        description="大脑调度策略 (本地/云端切换规则)"
    )

    providers: Dict[str, LLMConfig] = Field(
        default_factory=lambda: {
            "deepseek": LLMConfig(
                api_key="",
                base_url="https://api.deepseek.com",
                model="deepseek-chat"
            ),
            "openai": LLMConfig(
                api_key="",
                base_url="https://api.openai.com/v1",
                model="gpt-3.5-turbo"
            )
        },
        description="LLM 服务商配置列表"
    )
    
    persona: PersonaConfig = Field(
        default_factory=PersonaConfig,
        description="数字生命人设配置"
    )
    mock_response: str = Field(
        default="我听见你的心跳了呢~ 今天想和Selrena聊什么呀？",
        description="情感模拟模式回复模板（{user} 可替换用户输入片段）"
    )
    memory: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "model_path": ""},
        description="长期记忆模块的配置，包括是否启用和模型路径"
    )
    
    @property
    def llm(self) -> LLMConfig:
        """获取当前激活的 LLM 配置 (兼容旧代码接口)"""
        return self.providers.get(self.active_provider, next(iter(self.providers.values())))

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
