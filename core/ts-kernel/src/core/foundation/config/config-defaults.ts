/**
 * 默认配置模板
 * 用于首次运行或命令行工具生成完整的带注释 YAML 配置文件。
 *
 * 调用入口：ConfigManager.generateDefaults()
 */

/** system.yaml — 系统级配置（合并原 app + kernel） */
export const SYSTEM_YAML_TEMPLATE = `# ╔════════════════════════════════════════════════════════════╗
# ║  Cradle Selrena — 系统配置 (system.yaml)                  ║
# ║  端口号 / IPC 通信 / 日志级别 / 模块生命周期 / 插件沙箱    ║
# ╚════════════════════════════════════════════════════════════╝

# 应用显示名称
app_name: "Cradle Selrena"

# 语义化版本号（仅展示，不影响运行行为）
app_version: "0.1.0"

# 全局日志级别：debug | info | warn | error
log_level: "debug"

# ── 目录路径（均相对于项目根目录） ────────────────────────────

# 持久化数据目录（数据库、记忆等）
data_dir: "data"

# 日志输出目录
log_dir: "logs"

# 自动备份存放目录
backup_dir: "data/backup"

# 自动备份间隔（小时），0 = 不备份
auto_backup_interval_hours: 24

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ipc — TS ↔ Python 进程间通信
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ipc:
  bind_address: "tcp://127.0.0.1:8765" # ZMQ 绑定地址
  request_timeout_ms: 30000            # 单次请求超时（ms）
  retry_count: 2                       # 请求失败重试次数
  retry_interval_ms: 2000              # 重试间隔（ms）
  heartbeat_interval_ms: 5000          # Python 心跳检测间隔（ms）

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  lifecycle — 模块启停顺序
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lifecycle:
  start_timeout_ms: 30000
  stop_timeout_ms: 30000
  module_start_order:
    - config
    - persistence
    - ipc
    - python_ai
    - plugins
    - life_clock
  module_stop_order:
    - life_clock
    - plugins
    - python_ai
    - ipc
    - persistence
    - config

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  plugin — 插件系统
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

plugin:
  plugin_root_dir: "plugins"
  sandbox:
    enable_isolation: true
    timeout_ms: 5000
    allow_native_modules: false
  default_permissions:
    - CHAT_SEND
    - MEMORY_READ
    - MEMORY_WRITE
    - CONFIG_READ_SELF
    - CONFIG_WRITE_SELF
    - CONFIG_READ_GLOBAL
    - EVENT_SUBSCRIBE
  plugin_blacklist: []
`;

/** persona.yaml — 角色人格与 AI 层配置 */
export const PERSONA_YAML_TEMPLATE = `# ╔════════════════════════════════════════════════════════════╗
# ║  Cradle Selrena — 人设配置 (persona.yaml)                 ║
# ║  包含人格定义 / 推理参数 / LLM 提供商配置                  ║
# ║  ⚠ 本文件结构为 TS↔Python IPC 契约，请勿随意变更层级       ║
# ╚════════════════════════════════════════════════════════════╝

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  persona — 角色人格定义
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

persona:
  # ── 基础档案 ─────────────────────────────────────────────────────────────
  # 只保留最小身份锚定，性格/外观/风格等人格血肉完全由 knowledge-base.json 承载
  base:
    name: "Selrena"                    # 角色正式名（英文）
    nickname: "月见"                   # 角色昵称（中文）

  # ── 人格模式 ─────────────────────────────────────────────────────────────
  # api          → 知识库提供所有风格引导 + minimal 提示词锚定
  # local_base   → 同 api（使用本地基础模型，无专项微调）
  # local_finetune → 说话风格已烘焙到权重，跳过人设知识库检索，使用极简提示词
  persona_mode: "api"

  # ── 安全策略 ──────────────────────────────────────────────
  safety:
    taboos: ""                         # 禁忌规则（自由文本）
    forbidden_phrases: []              # 严格禁止出现的短语
    forbidden_regex: []                # 禁止匹配的正则表达式

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  inference — 推理引擎参数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

inference:
  # ── 模型参数 ──────────────────────────────────────────────
  model:
    local_model_path: ""               # 本地模型路径（仅 api_type=local 时生效）
    max_tokens: 1024                   # 单次生成最大 token 数
    temperature: 0.8                   # 采样温度（0=确定性 ~ 2=最大随机）
    top_p: 0.9                         # 核采样概率阈值
    frequency_penalty: 0.0             # 频率惩罚因子（-2 ~ 2）

  # ── 生命时钟 / 注意力管理 ─────────────────────────────────
  life_clock:
    focused_interval_ms: 10000         # 焦点模式心跳间隔（ms）
    ambient_interval_ms: 45000         # 环境模式心跳间隔（ms）
    default_mode: "standby"            # 启动时默认模式：standby | ambient | focused
    focus_duration_ms: 20000           # 焦点超时时长（ms），超时后回落到默认模式
    ingress_debounce_ms: 1400          # 普通消息防抖窗口（ms）
    ingress_focused_debounce_ms: 700   # 焦点模式防抖窗口（ms）
    ingress_max_batch_messages: 4      # 单批次最大消息条数
    ingress_max_batch_items: 24        # 单批次最大媒体项数
    summon_keywords:                   # 唤醒关键词列表
      - "月见"
      - "selrena"
    focus_on_any_chat: false           # true = 任意消息都触发焦点（无需唤醒词）
    active_thought_modes: []           # 允许主动思维的模式列表（空 = 禁用）
    # 注意：来源类型的注意力策略（source_focus_policies）由各 Vessel 插件自行注册，不在此处配置

  # ── 对话记忆规则 ──────────────────────────────────────────
  memory:
    max_recall_count: 5                # 单次检索最大记忆条数
    retention_days: 30                 # 记忆保留天数
    context_limit: 6                   # 提示词中携带的历史条数上限
    conversation_window: 12            # 触发摘要前的最大对话轮数
    summary_trigger_count: 18          # 触发自动摘要的消息条数
    summary_keep_recent_count: 6       # 摘要时保留的最近消息数
    summary_max_chars: 2400            # 摘要文本最大字符数

  # ── 多模态处理 ──────────────────────────────────────────
  multimodal:
    enabled: false                     # 是否启用多模态输入
    strategy: "specialist_then_core"   # core_direct | specialist_then_core
    max_items: 6                       # 单次最大媒体项
    core_model: "deepseek/chat"        # 主推理模型（provider/alias 格式）
    image_model: ""                    # 图像专家模型（如 qwen/vision）
    video_model: ""                    # 视频专家模型

  # ── 动作流（Live2D 联动） ─────────────────────────────────
  action_stream:
    enabled: false                     # 是否启用动作流
    channel: "live2d"                  # 渲染通道

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  llm — LLM 提供商配置
#  API Key 优先从 secret/secrets.yaml 自动注入，此处可留空
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

llm:
  api_type: "deepseek"                 # 主 API 协议：openai | azure | anthropic | deepseek | local
  base_url: "https://api.deepseek.com" # 主 API 端点
  temperature: 0.7                     # 主采样温度
  # api_key: ""                        # 留空，由 secrets.yaml 注入
  models:
    chat: "deepseek-chat"              # 默认模型（provider_key=None 时使用）

  # 多提供商配置（按需添加）
  # provider_key 格式：
  #   "deepseek"      → providers.deepseek.models 第一个模型
  #   "deepseek/chat" → providers.deepseek.models.chat
  # providers:
  #   deepseek:
  #     api_type: "deepseek"
  #     base_url: "https://api.deepseek.com"
  #     temperature: 0.7
  #     models:
  #       chat: "deepseek-chat"
  #   qwen:
  #     api_type: "openai"
  #     base_url: "https://dashscope.aliyuncs.com/compatible-mode"
  #     temperature: 0.7
  #     models:
  #       text: "qwen3.5-plus"
  #       vision: "qwen-vl-max"
`;

/** secret/secrets.example.yaml — 敏感信息示例文件 */
export const SECRETS_EXAMPLE_YAML_TEMPLATE = `# ╔════════════════════════════════════════════════════════════╗
# ║  敏感信息配置（请勿提交到版本控制）                        ║
# ║  复制本文件为 secrets.yaml 并填入真实凭据                  ║
# ╚════════════════════════════════════════════════════════════╝

# LLM API Key（按提供商名称自动注入到 persona.yaml 中）
providers:
  deepseek:
    api_key: "sk-..."
  qwen:
    api_key: "sk-..."
  openai:
    api_key: "sk-..."

# NapCat 适配器凭据
napcat:
  token: ""
`;

/** active-plugins.yaml — 启用的插件列表 */
export const ENABLED_PLUGINS_YAML_TEMPLATE = `# 启用的插件列表（按数组顺序加载）
enabled_plugins: []
`;
