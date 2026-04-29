import { z } from 'zod';

export const VTubeStudioPluginConfigSchema = z
  .object({
    transport: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(8001),
      })
      .default({}),
    features: z
      .object({
        enabled: z.boolean().default(false),
      })
      .default({}),
  })
  .passthrough();

export type VTubeStudioPluginConfig = z.infer<typeof VTubeStudioPluginConfigSchema>;
