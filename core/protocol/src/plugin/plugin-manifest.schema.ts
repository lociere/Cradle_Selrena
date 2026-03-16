/**
 * Plugin manifest schema used by the kernel plugin manager.
 *
 * 规范见 docs/目录中的插件开发规范。
 */
import { z } from "zod";

export const PluginManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  author: z.string().optional(),
  category: z.string().optional(),
  main: z.string(),
  minAppVersion: z.string().default("0.0.0"),
  permissions: z.array(z.string()).default([]),
});

export type PluginManifest = z.infer<typeof PluginManifestSchema>;
