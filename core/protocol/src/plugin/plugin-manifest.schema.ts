/**
 * Plugin manifest schema used by the kernel plugin manager.
 *
 * 规范见 docs/目录中的插件开发规范。
 */
import { z } from "zod";
import { Permission } from "../core";

export const PluginManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  author: z.string().optional(),
  /**
   * 自由文本，仅作人类可读的简短描述，内核不做任何语义解释。
   * 推荐用 tags 替代 category 来表达多维度属性。
   */
  category: z.string().optional(),
  /**
   * 自由标签数组，描述插件的角色与特性。
   * 内核不作任何约束，开发者可自定义任意标签组合，例如：
   *   ['adapter', 'websocket', 'qq']  或  ['tool', 'search', 'mcp']
   */
  tags: z.array(z.string()).default([]),
  main: z.string(),
  minAppVersion: z.string().default("0.0.0"),
  permissions: z.array(z.nativeEnum(Permission)).default([]),
});

export type PluginManifest = z.infer<typeof PluginManifestSchema>;
