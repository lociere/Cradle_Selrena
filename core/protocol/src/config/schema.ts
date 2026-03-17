/**
 * 配置Schema定义（供 TypeScript / Runtime 校验使用）
 * 与 Python AI 层的 Pydantic Config 保持一致。
 */
import { z } from "zod";

export const BasePersonaSchema = z.object({
  name: z.string(),
  nickname: z.string(),
  age: z.number().int().min(0),
  gender: z.string(),
  core_identity: z.string(),
  self_description: z.string(),
});
export type BasePersona = z.infer<typeof BasePersonaSchema>;

export const PersonaConfigSchema = z.object({
  base: BasePersonaSchema,
  character_traits: z.record(z.string(), z.number().int().min(0).max(10)),
  behavior_rules: z.array(z.string()),
  boundary_limits: z.array(z.string()),
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
  thought_interval_ms: z.number().int().min(1000),
  sleep_interval_ms: z.number().int().min(1000),
});
export type LifeClockConfig = z.infer<typeof LifeClockConfigSchema>;

export const MemoryRulesConfigSchema = z.object({
  max_recall_count: z.number().int().min(1),
  retention_days: z.number().int().min(1),
  context_limit: z.number().int().min(1),
});
export type MemoryRulesConfig = z.infer<typeof MemoryRulesConfigSchema>;

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
  }),
  llm: LLMConfigSchema.optional(),
});
export type GlobalAIConfig = z.infer<typeof GlobalAIConfigSchema>;
