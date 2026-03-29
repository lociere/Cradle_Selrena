/**
 * 全局配置 Schema（内核层）
 * 组合 protocol 层各子 Schema 为运行时使用的顶级结构
 *
 * 三大配置域映射到三个 YAML 文件：
 *   app    → configs/app.yaml
 *   ai     → configs/ai.yaml
 *   kernel → configs/kernel.yaml
 */
import { z } from "zod";
import {
  AppConfigSchema,
  GlobalAIConfigSchema,
  KernelConfigSchema,
} from "@cradle-selrena/protocol";

/** 运行时全局配置根 Schema */
export const GlobalConfigSchema = z.object({
  /** 应用元信息与目录路径 */
  app: AppConfigSchema,
  /** Python AI 层全量配置（人格 · 推理 · LLM 提供商） */
  ai: GlobalAIConfigSchema,
  /** TS 内核运行时配置（IPC · 生命周期 · 插件沙箱） */
  kernel: KernelConfigSchema,
});

export type GlobalConfig = z.infer<typeof GlobalConfigSchema>;
