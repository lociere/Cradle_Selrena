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
        group_policy: z
          .enum(['all', 'mention_only', 'wake_word_only'])
          .default('wake_word_only'),
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
  })
  .passthrough(); // 保留 speech/memory 等扩展字段

export type NapcatPluginConfig = z.infer<typeof NapcatPluginConfigSchema>;
