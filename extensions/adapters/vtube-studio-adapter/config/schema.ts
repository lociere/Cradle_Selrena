import { z } from 'zod';

export const VTubeStudioExpressionMappingSchema = z
  .object({
    expression_file: z.string().default(''),
    hotkey_id: z.string().default(''),
  })
  .default({});

export const VTubeStudioAdapterConfigSchema = z
  .object({
    connection: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(8001),
        reconnect_interval_ms: z.coerce.number().int().min(1000).default(5000),
        max_reconnect_attempts: z.coerce.number().int().min(0).default(0),
      })
      .default({}),
    auth: z
      .object({
        plugin_name: z.string().default('Cradle Selrena'),
        plugin_developer: z.string().default('Selrena Team'),
        auth_token: z.string().default(''),
      })
      .default({}),
    emotion_mapping: z.record(z.string(), VTubeStudioExpressionMappingSchema).default({
      happy: { expression_file: 'happy.exp3.json', hotkey_id: '' },
      sad: { expression_file: 'sad.exp3.json', hotkey_id: '' },
      angry: { expression_file: 'angry.exp3.json', hotkey_id: '' },
      neutral: { expression_file: 'neutral.exp3.json', hotkey_id: '' },
      surprised: { expression_file: 'surprised.exp3.json', hotkey_id: '' },
      thinking: { expression_file: 'thinking.exp3.json', hotkey_id: '' },
    }),
  })
  .passthrough();

export type VTubeStudioAdapterConfig = z.infer<typeof VTubeStudioAdapterConfigSchema>;

