/**
 * Cradle Selrena — 全局配置 Schema
 *
 * 所有配置项通过 Zod Schema 定义并进行运行时校验。
 * 三大配置域：
 *   app    — 应用元信息与目录路径
 *   ai     — Python AI 层全量配置（人格 · 推理 · LLM 提供商）
 *   kernel — TS 内核运行时（IPC · 生命周期 · 插件沙箱）
 *
 * 约定：
 *   - 带 .default() 的字段在 YAML 中可省略，自动填充默认值
 *   - 不带 .default() 的字段为必填，缺失时校验报错
 */
import { z } from "zod";

// ═══════════════════════════════════════════════════════════════
//  app — 应用元信息与目录路径
// ═══════════════════════════════════════════════════════════════

/** 应用级配置：名称、版本、日志、目录 */
export const AppConfigSchema = z.object({
  /** 应用显示名称 */
  app_name: z.string().default("Cradle Selrena"),
  /** 语义化版本号（仅展示） */
  app_version: z.string().default("0.1.0"),
  /** 全局日志级别 */
  log_level: z.enum(["debug", "info", "warn", "error"]).default("info"),
  /** 持久化数据根目录（相对项目根） */
  data_dir: z.string().default("data"),
  /** 日志输出目录（相对项目根） */
  log_dir: z.string().default("logs"),
  /** 自动备份存放目录（相对项目根） */
  backup_dir: z.string().default("data/backup"),
  /** 自动备份间隔（小时），0 = 不备份 */
  auto_backup_interval_hours: z.number().int().min(0).default(24),
});
export type AppConfig = z.infer<typeof AppConfigSchema>;

// ═══════════════════════════════════════════════════════════════
//  ai — Python AI 层配置
// ═══════════════════════════════════════════════════════════════

// ── 人格定义 (persona) ────────────────────────────────────────

/** 角色基础档案（身份锚定最小集，性格/外观等血肉由知识库承载） */
export const BasePersonaSchema = z.object({
  /** 角色正式名（英文 / 拼音） */
  name: z.string(),
  /** 角色昵称 / 中文名 */
  nickname: z.string(),
  /** 角色定位说明 */
  role: z.string(),
  /** 外观年龄 */
  apparent_age: z.string(),
  /** 性别 */
  gender: z.string(),
});
export type BasePersona = z.infer<typeof BasePersonaSchema>;

/** 对话风格策略 */
export const DialoguePolicySchema = z.object({
  /** 语言风格指导 */
  dialogue_style: z.string(),
  /** 情绪标签输出规则 */
  emotion_control: z.string(),
});
export type DialoguePolicy = z.infer<typeof DialoguePolicySchema>;

/** 安全策略：禁忌内容 / 禁止用语 */
export const SafetyPolicySchema = z.object({
  /** 自由文本形式的禁忌规则 */
  taboos: z.string(),
  /** 严格禁止出现的短语列表 */
  forbidden_phrases: z.array(z.string()).default([]),
  /** 禁止匹配的正则表达式列表 */
  forbidden_regex: z.array(z.string()).default([]),
});
export type SafetyPolicy = z.infer<typeof SafetyPolicySchema>;

/** 完整人格配置（身份 + 对话协议 + 安全红线，性格血肉由知识库承载） */
export const PersonaConfigSchema = z.object({
  base: BasePersonaSchema,
  dialogue: DialoguePolicySchema,
  safety: SafetyPolicySchema,
});
export type PersonaConfig = z.infer<typeof PersonaConfigSchema>;

// ── 推理参数 (inference) ──────────────────────────────────────

/** 本地 / 远程模型参数 */
export const ModelConfigSchema = z.object({
  /** 本地模型文件路径（仅 api_type=local 时生效） */
  local_model_path: z.string().default(""),
  /** 单次生成最大 token 数 */
  max_tokens: z.number().int().min(1).default(1024),
  /** 采样温度（0 = 确定性，2 = 最大随机） */
  temperature: z.number().min(0).max(2).default(0.8),
  /** 核采样概率阈值 */
  top_p: z.number().min(0).max(1).default(0.9),
  /** 频率惩罚因子 */
  frequency_penalty: z.number().min(-2).max(2).default(0.0),
});
export type ModelConfig = z.infer<typeof ModelConfigSchema>;

/** 注意力来源策略枚举（导出供插件使用） */
export const SourceFocusPolicyEnum = z.enum([
  "always_focused",
  "wake_word_focus",
  "wake_word_focus_with_timeout",
  "chat_or_wake_focus_with_timeout",
  "ignore",
]);
export type SourceAttentionPolicy = z.infer<typeof SourceFocusPolicyEnum>;

/** 注意力模式枚举 */
const AttentionModeEnum = z.enum(["standby", "ambient", "focused"]);

/** 生命时钟 / 注意力管理配置 */
export const LifeClockConfigSchema = z.object({
  /** 焦点模式下的心跳间隔（ms） */
  focused_interval_ms: z.number().int().min(1000).default(10000),
  /** 环境模式下的心跳间隔（ms） */
  ambient_interval_ms: z.number().int().min(1000).default(45000),
  /** 启动时默认注意力模式 */
  default_mode: AttentionModeEnum.default("standby"),
  /** 焦点模式持续时长（ms），超时后回落到默认模式 */
  focus_duration_ms: z.number().int().min(1000).default(20000),
  /** 普通消息防抖时间窗口（ms） */
  ingress_debounce_ms: z.number().int().min(100).default(1400),
  /** 焦点模式下的防抖时间窗口（ms），应小于普通值以提高响应速度 */
  ingress_focused_debounce_ms: z.number().int().min(50).default(700),
  /** 单次批处理最大消息条数 */
  ingress_max_batch_messages: z.number().int().min(1).default(4),
  /** 单次批处理最大媒体项数 */
  ingress_max_batch_items: z.number().int().min(1).default(24),
  /** 唤醒关键词列表 */
  summon_keywords: z.array(z.string()).default([]),
  /** 是否任意聊天都触发焦点（true = 无需唤醒词） */
  focus_on_any_chat: z.boolean().default(false),
  /** 允许触发主动思维的注意力模式列表（空 = 禁用主动思维） */
  active_thought_modes: z.array(AttentionModeEnum).default([]),
});
export type LifeClockConfig = z.infer<typeof LifeClockConfigSchema>;

/** 对话记忆管理规则 */
export const MemoryRulesConfigSchema = z.object({
  /** 单次回忆检索最大条数 */
  max_recall_count: z.number().int().min(1).default(5),
  /** 记忆保留天数（超期自动归档） */
  retention_days: z.number().int().min(1).default(30),
  /** 上下文窗口大小（提示词中携带的历史条数上限） */
  context_limit: z.number().int().min(1).default(6),
  /** 对话窗口大小（触发摘要前的最大对话轮数） */
  conversation_window: z.number().int().min(1).default(12),
  /** 触发自动摘要的消息条数阈值 */
  summary_trigger_count: z.number().int().min(2).default(18),
  /** 摘要时保留最近几条消息不参与摘要 */
  summary_keep_recent_count: z.number().int().min(1).default(6),
  /** 摘要文本最大字符数 */
  summary_max_chars: z.number().int().min(256).default(2400),
});
export type MemoryRulesConfig = z.infer<typeof MemoryRulesConfigSchema>;

/** 多模态处理策略 */
export const MultimodalConfigSchema = z.object({
  /** 是否启用多模态输入处理 */
  enabled: z.boolean().default(false),
  /** 处理策略：core_direct = 主模型直接处理 | specialist_then_core = 专家预处理后传主模型 */
  strategy: z.enum(["core_direct", "specialist_then_core"]).default("specialist_then_core"),
  /** 单次请求最大媒体项数 */
  max_items: z.number().int().min(1).default(6),
  /** 主推理模型名称 */
  core_model: z.string().default("deepseek"),
  /** 图像专家模型名称 */
  image_model: z.string().default(""),
  /** 视频专家模型名称 */
  video_model: z.string().default(""),
});
export type MultimodalConfig = z.infer<typeof MultimodalConfigSchema>;

/** 动作流（Live2D 表情 / 动作联动）配置 */
export const ActionStreamConfigSchema = z.object({
  /** 是否启用动作流 */
  enabled: z.boolean().default(false),
  /** 渲染通道 */
  channel: z.enum(["live2d"]).default("live2d"),
});
export type ActionStreamConfig = z.infer<typeof ActionStreamConfigSchema>;

// ── LLM 提供商 (llm) ─────────────────────────────────────────

/** 单个 LLM 提供商配置 */
const LLMProviderSchema = z
  .object({
    /** API 协议类型 */
    api_type: z.string().default("openai"),
    /** API Key（优先从 secrets.yaml 注入，此处可留空） */
    api_key: z.string().optional(),
    /** API 端点地址 */
    base_url: z.string().optional(),
    /** 模型字典：alias → 模型 ID，无 alias 时取第一个值 */
    models: z.record(z.string(), z.string()),
    /** 采样温度覆盖 */
    temperature: z.number().min(0).max(2).optional(),
    /** 自定义 HTTP 方法 */
    request_method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).optional(),
    /** 自定义请求路径 */
    request_path: z.string().optional(),
    /** 自定义请求头 */
    request_headers: z.record(z.string(), z.string()).optional(),
    /** 请求体模板（支持 {prompt} / {model} / {temperature} 占位符） */
    request_body_template: z.string().optional(),
    /** 响应解析路径（点分隔，例如 choices.0.text） */
    response_extract: z.string().optional(),
  })
  .strict(); // 拒绝旧 model 字段等备用键

/** LLM 提供商配置（主提供商 + 多备选） */
export const LLMConfigSchema = z.object({
  /** 主 API 协议类型 */
  api_type: z.string().default("openai"),
  /** 主 API Key（优先从 secrets.yaml 注入） */
  api_key: z.string().optional(),
  /** 主 API 端点 */
  base_url: z.string().optional(),
  /** 根配置模型字典：alias → 模型 ID；provider_key=None 时取第一个值 */
  models: z.record(z.string(), z.string()).optional(),
  /** 主采样温度 */
  temperature: z.number().min(0).max(2).optional(),
  /** 多提供商配置映射（key = 提供商名称） */
  providers: z.record(z.string(), LLMProviderSchema).optional(),
  /** 自定义 HTTP 方法 */
  request_method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).optional(),
  /** 自定义请求路径 */
  request_path: z.string().optional(),
  /** 自定义请求头 */
  request_headers: z.record(z.string(), z.string()).optional(),
  /** 请求体模板 */
  request_body_template: z.string().optional(),
  /** 响应解析路径 */
  response_extract: z.string().optional(),
});
export type LLMConfig = z.infer<typeof LLMConfigSchema>;

// ── AI 配置聚合 ───────────────────────────────────────────────

/** Python AI 层全量配置（通过 IPC 传递，结构为 ABI 契约） */
export const GlobalAIConfigSchema = z.object({
  /** 角色人格定义 */
  persona: PersonaConfigSchema,
  /** 推理引擎参数 */
  inference: z.object({
    model: ModelConfigSchema,
    life_clock: LifeClockConfigSchema,
    memory: MemoryRulesConfigSchema,
    multimodal: MultimodalConfigSchema,
    action_stream: ActionStreamConfigSchema,
  }),
  /** LLM 提供商配置 */
  llm: LLMConfigSchema.optional(),
});
export type GlobalAIConfig = z.infer<typeof GlobalAIConfigSchema>;

// ═══════════════════════════════════════════════════════════════
//  kernel — TS 内核运行时配置
// ═══════════════════════════════════════════════════════════════

/** IPC 通信层配置（TS ↔ Python） */
export const IPCConfigSchema = z.object({
  /** ZMQ 绑定地址（格式：tcp://host:port） */
  bind_address: z.string().default("tcp://127.0.0.1:8765"),
  /** 单次 IPC 请求超时（ms） */
  request_timeout_ms: z.number().int().min(1000).default(30000),
  /** 请求失败重试次数 */
  retry_count: z.number().int().min(0).default(2),
  /** 重试间隔（ms） */
  retry_interval_ms: z.number().int().min(0).default(2000),
  /** Python 层心跳检测间隔（ms） */
  heartbeat_interval_ms: z.number().int().min(1000).default(5000),
});
export type IPCConfig = z.infer<typeof IPCConfigSchema>;

/** 模块生命周期管理配置 */
export const LifecycleConfigSchema = z.object({
  /** 模块启动总超时（ms） */
  start_timeout_ms: z.number().int().min(1000).default(30000),
  /** 模块停止总超时（ms） */
  stop_timeout_ms: z.number().int().min(1000).default(30000),
  /** 模块启动顺序（按数组顺序依次启动） */
  module_start_order: z.array(z.string()).default([
    "config", "persistence", "ipc", "python_ai", "plugins", "life_clock",
  ]),
  /** 模块停止顺序（按数组顺序依次停止） */
  module_stop_order: z.array(z.string()).default([
    "life_clock", "plugins", "python_ai", "ipc", "persistence", "config",
  ]),
});
export type LifecycleConfig = z.infer<typeof LifecycleConfigSchema>;

/** 插件沙箱配置 */
const PluginSandboxSchema = z.object({
  /** 是否启用插件隔离 */
  enable_isolation: z.boolean().default(true),
  /** 插件 onActivate / onDeactivate 超时（ms） */
  timeout_ms: z.number().int().min(0).default(5000),
  /** 是否允许插件加载 native 模块 */
  allow_native_modules: z.boolean().default(false),
});

/** 插件系统配置 */
export const PluginConfigSchema = z.object({
  /** 插件根目录（相对项目根） */
  plugin_root_dir: z.string().default("plugins"),
  /** 沙箱策略 */
  sandbox: PluginSandboxSchema.default({}),
  /** 新插件默认获得的权限列表 */
  default_permissions: z.array(z.string()).default([
    "CHAT_SEND", "MEMORY_READ", "MEMORY_WRITE",
    "CONFIG_READ_SELF", "CONFIG_WRITE_SELF", "CONFIG_READ_GLOBAL",
    "EVENT_SUBSCRIBE",
  ]),
  /** 插件黑名单（ID 列表，阻止加载） */
  plugin_blacklist: z.array(z.string()).default([]),
});
export type PluginConfig = z.infer<typeof PluginConfigSchema>;

/** 入站防护配置（速率限制 · 熔断 · 就绪守卫） */
export const IngressGateConfigSchema = z.object({
  /** 单来源滑动窗口内最大请求数 */
  rate_limit_per_source: z.number().int().min(1).default(30),
  /** 滑动窗口时长（ms） */
  rate_limit_window_ms: z.number().int().min(1000).default(60000),
  /** 全局最大并发处理请求数 */
  max_concurrent_requests: z.number().int().min(1).default(10),
  /** 连续失败几次后触发熔断 */
  circuit_breaker_threshold: z.number().int().min(1).default(5),
  /** 熔断恢复等待时间（ms） */
  circuit_breaker_recovery_ms: z.number().int().min(1000).default(30000),
});
export type IngressGateConfig = z.infer<typeof IngressGateConfigSchema>;

/** TS 内核运行时配置聚合 */
export const KernelConfigSchema = z.object({
  /** IPC 通信配置 */
  ipc: IPCConfigSchema.default({}),
  /** 模块生命周期 */
  lifecycle: LifecycleConfigSchema.default({}),
  /** 插件系统 */
  plugin: PluginConfigSchema.default({}),
  /** 入站防护（速率限制 · 熔断 · 就绪守卫） */
  ingress_gate: IngressGateConfigSchema.default({}),
});
export type KernelConfig = z.infer<typeof KernelConfigSchema>;

// ═══════════════════════════════════════════════════════════════
//  知识库（独立加载，不属于全局三大配置域）
// ═══════════════════════════════════════════════════════════════

/** 知识条目范围 */
export const KnowledgeScopeSchema = z.enum(["persona", "general"]);
export type KnowledgeScope = z.infer<typeof KnowledgeScopeSchema>;

/** 单条知识条目 */
export const KnowledgeEntrySchema = z.object({
  /** 唯一标识 */
  entry_id: z.string().min(1),
  /** 知识范围：persona = 角色专属 | general = 通用 */
  scope: KnowledgeScopeSchema,
  /** 知识内容文本 */
  content: z.string().min(1),
  /** 检索优先级（1-100，越大越优先） */
  priority: z.number().int().min(1).max(100),
  /** 标签列表（辅助检索） */
  tags: z.array(z.string().min(1)).default([]),
  /** 是否启用 */
  enabled: z.boolean().default(true),
});
export type KnowledgeEntry = z.infer<typeof KnowledgeEntrySchema>;

/** 知识检索配置 */
export const KnowledgeRetrievalConfigSchema = z.object({
  /** 角色知识检索 top-k */
  persona_top_k: z.number().int().min(1).max(50).default(5),
  /** 通用知识检索 top-k */
  general_top_k: z.number().int().min(1).max(50).default(5),
  /** 最低相似度阈值 */
  min_score: z.number().min(0).max(1).default(0.3),
  /** 关键词匹配权重 */
  keyword_weight: z.number().min(0).default(1.0),
  /** 标签匹配权重 */
  tag_weight: z.number().min(0).default(0.5),
  /** 优先级权重 */
  priority_weight: z.number().min(0).default(0.3),
});
export type KnowledgeRetrievalConfig = z.infer<typeof KnowledgeRetrievalConfigSchema>;

/** 知识库完整配置 */
export const KnowledgeBaseConfigSchema = z.object({
  version: z.string().min(1),
  retrieval: KnowledgeRetrievalConfigSchema,
  entries: z.array(KnowledgeEntrySchema),
});
export type KnowledgeBaseConfig = z.infer<typeof KnowledgeBaseConfigSchema>;
