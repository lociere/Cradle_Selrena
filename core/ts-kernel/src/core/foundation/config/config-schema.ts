/**
 * 全局配置 Schema（内核层）
 * 组合 protocol 层各子 Schema 为运行时使用的顶级结构
 *
 * 两大配置域映射到两个 YAML 文件：
 *   system  → configs/system.yaml   (系统级：端口 / IPC / 日志 / 生命周期 / 插件)
 *   persona → configs/persona.yaml  (角色人格与 AI 层配置)
 */
import { z } from "zod";
import {
  SystemConfigSchema,
  GlobalAIConfigSchema,
} from "@cradle-selrena/protocol";

/** 运行时全局配置根 Schema */
export const GlobalConfigSchema = z.object({
  /** 系统级配置（合并原 app + kernel） */
  system: SystemConfigSchema,
  /** 角色人格与 AI 层配置（人格 · 推理 · LLM 提供商） */
  persona: GlobalAIConfigSchema,
});

export type GlobalConfig = z.infer<typeof GlobalConfigSchema>;
