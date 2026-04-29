/**
 * Napcat Plugin Config Schema — config/schema.ts
 *
 * 对应配置文件：configs/plugins/napcat-qq.yaml
 */
import { z } from 'zod';

export const NapcatPluginConfigSchema = z
  .object({
    transport: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(6200),
        path: z.string().default('/'),
        access_token: z.string().default(''),
        access_token_env: z.string().default(''),
        /** true 时仅从 env 读取 token，不降级到明文配置，避免敏感信息泄露 */
        token_from_secrets: z.boolean().default(false),
      })
      .default({}),
    main_user: z
      .object({
        qq: z.string().default(''),
      })
      .default({}),
    ingress: z
      .object({
        ignore_self: z.boolean().default(true),
        private_enabled: z.boolean().default(true),
        group_enabled: z.boolean().default(true),
        wake_words: z.array(z.string()).default([]),
        strip_self_mention: z.boolean().default(true),
        strip_leading_wake_words: z.boolean().default(true),
        blocked_user_ids: z.array(z.string()).default([]),
        blocked_group_ids: z.array(z.string()).default([]),
        familiarity: z
          .object({
            private: z.number().default(10),
            group: z.number().default(6),
          })
          .default({}),
        /**
         * 唤醒后的焦点持续时长（毫秒），可选，供本插件覆盖内核全局值。
         * 不配置时使用内核全局配置 configs/persona.yaml → inference.life_clock.focus_duration_ms。
         */
        focus_duration_ms: z.number().int().positive().optional(),
        /**
         * 来源类型→注意力策略映射（插件激活时注入内核 LifeClockManager）。
         * 可选值: always_focused | wake_word_focus | wake_word_focus_with_timeout | chat_or_wake_focus_with_timeout | ignore
         */
        source_focus_policies: z
          .record(z.string(), z.string())
          .default({
            private: 'always_focused',
            group: 'wake_word_focus_with_timeout',
          }),

        multimodal: z
          .object({
            enabled: z.boolean().default(false),
          })
          .default({}),
      })
      .default({}),
    reply: z
      .object({
        enabled: z.boolean().default(true),
        mention_sender_in_group: z.boolean().default(false),
        quote_source_message: z.boolean().default(false),
        auto_escape: z.boolean().default(false),
      })
      .default({}),
    routing: z
      .object({
        session_partition: z
          .object({
            private: z.string().default('by_source'),
            group: z.string().default('by_source'),
          })
          .default({}),
      })
      .default({}),
    runtime: z
      .object({
        action_timeout_ms: z.number().default(15000),
        nickname_cache_ttl_ms: z.number().default(300000),
      })
      .default({}),
    memory: z
      .object({
        enabled: z.boolean().default(false),
        /** 唤醒时携带的群聊背景消息条数上限 */
        group_context_size: z.number().int().min(1).max(50).default(20),
      })
      .default({}),
  })
  .passthrough(); // 保留 speech 等扩展字段

export type NapcatPluginConfig = z.infer<typeof NapcatPluginConfigSchema>;
