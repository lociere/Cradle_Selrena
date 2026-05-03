/**
 * Example config schema for a custom extension.
 *
 * ExtensionManager loads configs/extension/<extension-id>.yaml,
 * validates it with this schema, and injects the parsed result into ctx.config.
 */
import { z } from 'zod';

export const MyExtensionConfigSchema = z
  .object({
    // Example network settings.
    server: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(8080),
      })
      .default({}),

    // Example feature flags.
    features: z
      .object({
        enabled: z.boolean().default(true),
      })
      .default({}),
  })
  .passthrough();

/** Typed config consumed by MyExtension. */
export type MyExtensionConfig = z.infer<typeof MyExtensionConfigSchema>;

