/**
 * 全局配置Schema
 * 与protocol层的配置类型100%对齐
 */
import { z } from "zod";
import {
  AppConfigSchema,
  GlobalAIConfigSchema,
  IPCConfigSchema,
  LifecycleConfigSchema,
  MemoryRulesConfigSchema,
  PluginConfigSchema,
} from "@cradle-selrena/protocol";

// 全局根配置Schema
export const GlobalConfigSchema = z.object({
  app: AppConfigSchema,
  ai: GlobalAIConfigSchema,
  ipc: IPCConfigSchema,
  lifecycle: LifecycleConfigSchema,
  memory: MemoryRulesConfigSchema,
  plugin: PluginConfigSchema,
});

export type GlobalConfig = z.infer<typeof GlobalConfigSchema>;
