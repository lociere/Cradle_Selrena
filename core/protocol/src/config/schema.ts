/**
 * 配置Schema定义（供 TypeScript / Runtime 校验使用）
 * 与 Python AI 层的 Pydantic Config 保持一致。
 */
import { z } from "zod";

export const BasePersonaSchema = z.object({
  name: z.string(),
  nickname: z.string(),
  role: z.string(),
  apparent_age: z.string(),
  gender: z.string(),
  appearance: z.string(),
  background: z.string(),
});
export type BasePersona = z.infer<typeof BasePersonaSchema>;

export const PersonaCoreSchema = z.object({
  personality: z.string(),
  character_core: z.string(),
  likes: z.string(),
});
export type PersonaCore = z.infer<typeof PersonaCoreSchema>;

export const DialoguePolicySchema = z.object({
  dialogue_style: z.string(),
  emotion_control: z.string(),
});
export type DialoguePolicy = z.infer<typeof DialoguePolicySchema>;

export const SafetyPolicySchema = z.object({
  taboos: z.string(),
  forbidden_phrases: z.array(z.string()),
  forbidden_regex: z.array(z.string()),
});
export type SafetyPolicy = z.infer<typeof SafetyPolicySchema>;

export const PersonaConfigSchema = z.object({
  base: BasePersonaSchema,
  core: PersonaCoreSchema,
  dialogue: DialoguePolicySchema,
  safety: SafetyPolicySchema,
});
export type PersonaConfig = z.infer<typeof PersonaConfigSchema>;

export const ModelConfigSchema = z.object({
  local_model_path: z.string(),
  max_tokens: z.number().int().min(1),
  temperature: z.number().min(0).max(2),
  top_p: z.number().min(0).max(1),
  frequency_penalty: z.number().min(-2).max(2),
});
export type ModelConfig = z.infer<typeof ModelConfigSchema>;

export const LifeClockConfigSchema = z.object({
  focused_interval_ms: z.number().int().min(1000),
  ambient_interval_ms: z.number().int().min(1000),
  default_mode: z.enum(["standby", "ambient", "focused"]),
  focus_duration_ms: z.number().int().min(1000),
  ingress_debounce_ms: z.number().int().min(100),
  ingress_focused_debounce_ms: z.number().int().min(50),
  ingress_max_batch_messages: z.number().int().min(1),
  ingress_max_batch_items: z.number().int().min(1),
  summon_keywords: z.array(z.string()),
  focus_on_any_chat: z.boolean(),
  active_thought_modes: z.array(z.enum(["standby", "ambient", "focused"])),
  source_focus_policies: z.record(
    z.string(),
    z.enum([
      "always_focused",
      "wake_word_focus",
      "wake_word_focus_with_timeout",
      "chat_or_wake_focus_with_timeout",
      "ignore",
    ])
  ).optional(),
});
export type LifeClockConfig = z.infer<typeof LifeClockConfigSchema>;

export const MemoryRulesConfigSchema = z.object({
  max_recall_count: z.number().int().min(1),
  retention_days: z.number().int().min(1),
  context_limit: z.number().int().min(1),
  conversation_window: z.number().int().min(1),
  summary_trigger_count: z.number().int().min(2),
  summary_keep_recent_count: z.number().int().min(1),
  summary_max_chars: z.number().int().min(256),
});
export type MemoryRulesConfig = z.infer<typeof MemoryRulesConfigSchema>;

export const MultimodalConfigSchema = z.object({
  enabled: z.boolean(),
  strategy: z.enum(["core_direct", "specialist_then_core"]),
  max_items: z.number().int().min(1),
  core_model: z.string(),
  image_model: z.string(),
  video_model: z.string(),
});
export type MultimodalConfig = z.infer<typeof MultimodalConfigSchema>;

export const ActionStreamConfigSchema = z.object({
  enabled: z.boolean(),
  channel: z.enum(["live2d"]),
  chunk_interval_ms: z.number().int().min(33),
  max_chunks_per_stream: z.number().int().min(1),
  emit_thinking_chunks: z.boolean(),
  emit_emotion_on_complete: z.boolean(),
});
export type ActionStreamConfig = z.infer<typeof ActionStreamConfigSchema>;

export const KnowledgeScopeSchema = z.enum(["persona", "general"]);
export type KnowledgeScope = z.infer<typeof KnowledgeScopeSchema>;

export const KnowledgeEntrySchema = z.object({
  entry_id: z.string().min(1),
  scope: KnowledgeScopeSchema,
  content: z.string().min(1),
  priority: z.number().int().min(1).max(100),
  tags: z.array(z.string().min(1)).default([]),
  enabled: z.boolean().default(true),
  source: z.string().min(1).default("manual"),
  updated_at: z.string().min(1).default(""),
});
export type KnowledgeEntry = z.infer<typeof KnowledgeEntrySchema>;

export const KnowledgeRetrievalConfigSchema = z.object({
  persona_top_k: z.number().int().min(1).max(50),
  general_top_k: z.number().int().min(1).max(50),
  min_score: z.number().min(0).max(1),
  keyword_weight: z.number().min(0),
  tag_weight: z.number().min(0),
  priority_weight: z.number().min(0),
});
export type KnowledgeRetrievalConfig = z.infer<typeof KnowledgeRetrievalConfigSchema>;

export const KnowledgeBaseConfigSchema = z.object({
  version: z.string().min(1),
  retrieval: KnowledgeRetrievalConfigSchema,
  entries: z.array(KnowledgeEntrySchema),
});
export type KnowledgeBaseConfig = z.infer<typeof KnowledgeBaseConfigSchema>;

export const IPCConfigSchema = z.object({
  bind_address: z.string(),
  request_timeout_ms: z.number().int().min(1),
  retry_count: z.number().int().min(0),
  retry_interval_ms: z.number().int().min(0),
  heartbeat_interval_ms: z.number().int().min(1),
});
export type IPCConfig = z.infer<typeof IPCConfigSchema>;

export const LifecycleConfigSchema = z.object({
  start_timeout_ms: z.number().int().min(1),
  stop_timeout_ms: z.number().int().min(1),
  module_start_order: z.array(z.string()),
  module_stop_order: z.array(z.string()),
});
export type LifecycleConfig = z.infer<typeof LifecycleConfigSchema>;

export const PluginConfigSchema = z.object({
  plugin_root_dir: z.string(),
  sandbox: z.object({
    enable_isolation: z.boolean(),
    timeout_ms: z.number().int().min(0),
    allow_native_modules: z.boolean(),
  }),
  default_permissions: z.array(z.string()),
  plugin_blacklist: z.array(z.string()),
});
export type PluginConfig = z.infer<typeof PluginConfigSchema>;

export const AppConfigSchema = z.object({
  app_name: z.string(),
  app_version: z.string(),
  log_level: z.enum(["debug", "info", "warn", "error"]),
  data_dir: z.string(),
  log_dir: z.string(),
  backup_dir: z.string(),
  auto_backup_interval_hours: z.number().int().min(1),
});
export type AppConfig = z.infer<typeof AppConfigSchema>;

export const LLMConfigSchema = z.object({
  // API类型，例如：openai、azure、anthropic、deepseek、本地(local)
  api_type: z.string().default("openai"),
  // API key 或令牌
  api_key: z.string().optional(),
  // API endpoint（可选，用于企业/私有部署）
  base_url: z.string().optional(),
  // 其他可选参数
  model: z.string().optional(),
  temperature: z.number().min(0).max(2).optional(),

  // 可选：多 Provider 配置（例如 deepseek / qwen）
  providers: z.record(
    z.string(),
    z.object({
      api_type: z.string().default("openai"),
      api_key: z.string().optional(),
      base_url: z.string().optional(),
      model: z.string().optional(),
      temperature: z.number().min(0).max(2).optional(),
      request_method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).optional(),
      request_path: z.string().optional(),
      request_headers: z.record(z.string(), z.string()).optional(),
      request_body_template: z.string().optional(),
      response_extract: z.string().optional(),
    })
  ).optional(),

  // 请求自定义配置（可选）
  request_method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).optional(),
  request_path: z.string().optional(),
  request_headers: z.record(z.string(), z.string()).optional(),
  // 请求 body 模板，支持 {prompt} / {model} / {temperature} 等占位符
  request_body_template: z.string().optional(),

  // 响应解析路径，点分隔字段（例如 choices.0.text 或 result）
  response_extract: z.string().optional(),
});
export type LLMConfig = z.infer<typeof LLMConfigSchema>;

export const GlobalAIConfigSchema = z.object({
  persona: PersonaConfigSchema,
  inference: z.object({
    model: ModelConfigSchema,
    life_clock: LifeClockConfigSchema,
    memory: MemoryRulesConfigSchema,
    multimodal: MultimodalConfigSchema,
    action_stream: ActionStreamConfigSchema,
  }),
  llm: LLMConfigSchema.optional(),
});
export type GlobalAIConfig = z.infer<typeof GlobalAIConfigSchema>;
