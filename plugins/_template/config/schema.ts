/**
 * 插件配置 Schema — config/schema.ts
 *
 * 【必须存在】使用 Zod 声明配置结构。
 * PluginManager 在加载插件时自动从 configs/plugin/<plugin-id>.yaml
 * 读取配置并调用 configSchema.safeParse() 验证。
 *
 * 规范：
 *   - 所有字段提供 .default() 确保缺省值，避免运行时 undefined
 *   - 顶层使用 .passthrough() 保留未声明字段，方便未来扩展
 *   - 只做结构和类型约束，不写业务逻辑
 *   - 将 Schema 推断类型 export，供主插件类和子模块使用
 */
import { z } from 'zod';

export const MyPluginConfigSchema = z
  .object({
    // ── 示例字段，按需替换 ─────────────────────────────────────

    // 网络连接
    server: z
      .object({
        host: z.string().default('127.0.0.1'),
        port: z.coerce.number().int().positive().default(8080),
      })
      .default({}),

    // 功能开关
    features: z
      .object({
        enabled: z.boolean().default(true),
      })
      .default({}),
  })
  .passthrough();

/** 配置类型，在插件代码中使用 `MyPluginConfig` 替代裸 object */
export type MyPluginConfig = z.infer<typeof MyPluginConfigSchema>;
