/**
 * NapCat adapter config schema.
 *
 * Runtime config file: configs/extension/napcat-adapter.yaml
 */
import { z } from 'zod';

export const NapcatAdapterConfigSchema = z
  .object({
    transport: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(6200),
        path: z.string().default('/'),
        access_token: z.string().default(''),
        access_token_env: z.string().default(''),
        /** true 鏃朵粎浠?env 璇诲彇 token锛屼笉闄嶇骇鍒版槑鏂囬厤缃紝閬垮厤鏁忔劅淇℃伅娉勯湶 */
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
         * 鍞ら啋鍚庣殑鐒︾偣鎸佺画鏃堕暱锛堟绉掞級锛屽彲閫夛紝渚涙湰鎻掍欢瑕嗙洊鍐呮牳鍏ㄥ眬鍊笺€?
         * 涓嶉厤缃椂浣跨敤鍐呮牳鍏ㄥ眬閰嶇疆 configs/persona.yaml 鈫?inference.life_clock.focus_duration_ms銆?
         */
        focus_duration_ms: z.number().int().positive().optional(),
        /**
         * 鏉ユ簮绫诲瀷鈫掓敞鎰忓姏绛栫暐鏄犲皠锛堟彃浠舵縺娲绘椂娉ㄥ叆鍐呮牳 LifeClockManager锛夈€?
         * 鍙€夊€? always_focused | wake_word_focus | wake_word_focus_with_timeout | chat_or_wake_focus_with_timeout | ignore
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
        /** 鍞ら啋鏃舵惡甯︾殑缇よ亰鑳屾櫙娑堟伅鏉℃暟涓婇檺 */
        group_context_size: z.number().int().min(1).max(50).default(20),
      })
      .default({}),
  })
  .passthrough(); // 淇濈暀 speech 绛夋墿灞曞瓧娈?

export type NapcatAdapterConfig = z.infer<typeof NapcatAdapterConfigSchema>;

