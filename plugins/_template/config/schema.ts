/**
 * 插件配置 Schema — config/schema.ts
 *
 * 使用 Zod 声明配置结构。PluginManager 在加载插件时自动调用
 * configSchema.safeParse() 验证 configs/plugins/<plugin-id>.yaml 的内容。
 *
 * 规范：
 *   - 所有字段提供 .default() 确保缺省值，避免运行时 undefined
 *   - 使用 .passthrough() 保留未声明字段，方便未来扩展
 *   - 不要在 schema 里写业务逻辑，只做结构和类型约束
 */
import { z } from 'zod';

export const MyPluginConfigSchema = z
  .object({
    // ── 示例：网络连接配置 ──────────────────────────────────────
    server: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(8080),
      })
      .default({}),

    // ── 示例：功能开关 ──────────────────────────────────────────
    features: z
      .object({
        enabled: z.boolean().default(true),
      })
      .default({}),
  })
  .passthrough(); // 保留未声明字段，避免对配置扩展产生硬性限制

export type MyPluginConfig = z.infer<typeof MyPluginConfigSchema>;
