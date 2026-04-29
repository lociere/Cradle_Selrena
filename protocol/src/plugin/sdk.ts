/**
 * 插件 SDK 核心类型
 * 定义所有插件可见的接口契约，是 Soul-Vessel 架构的公共语言。
 * 此文件不得引入任何内核实现细节（平台协议、数据库、文件系统等）。
 */
import { z } from 'zod';
import type { ExtensionCommandContribution } from './plugin-manifest.schema';
export type { ExtensionCommandContribution } from './plugin-manifest.schema';

// ─────────────────────────────────────────────
// 感知系统
// ─────────────────────────────────────────────

/** 感知通道类型 */
export type SensoryType =
  | 'VISUAL'
  | 'AUDITORY'
  | 'TEXT'
  | 'SYSTEM'
  | 'SOMATOSENSORY'
  | 'EMOTIONAL';

/**
 * 通用感知事件 DTO
 * 所有外部刺激（消息、语音、系统心跳）的统一载体，
 * 由 Vessel 层清洗后填入，Soul 层只读此结构。
 */
// PerceptionEvent 由 Schema-First 契约统一定义，此处 re-export 供插件直接使用
import type { PerceptionEvent } from '../generated';
export type { PerceptionEvent };

// ─────────────────────────────────────────────
// 子代理 / MCP 工具
// ─────────────────────────────────────────────

/** MCP 工具描述 */
export interface MCPTool<TArgs = unknown> {
  name: string;
  description: string;
  parameters: z.ZodType<TArgs>;
  handler: (args: TArgs) => Promise<unknown> | unknown;
}

/** 子代理简档 */
export interface SubAgentProfile {
  id: string;
  name: string;
  /** 给主脑用于路由 Agent 的描述 */
  description: string;
  /** 该 Agent 注册时携带的 MCP 级别工具 */
  tools: MCPTool[];
  /** 执行操作后是否允许影响主脑的情绪/生成长期记忆（联觉纠缠） */
  memoryImpact?: boolean;
  /** 是否可以在生命周期中主动打断正在进行的流 */
  allowInterrupt?: boolean;
}

// ─────────────────────────────────────────────
// 沙箱资源接口
// ─────────────────────────────────────────────

/** 可销毁资源句柄 */
export interface IDisposable {
  dispose(): void | Promise<void>;
}

/** 插件专属轻量日志接口 */
export interface IPluginLogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;
}

export interface ExtensionCommandHandler {
  (...args: unknown[]): Promise<unknown> | unknown;
}

export interface ExtensionCommandMetadata {
  title?: string;
  category?: string;
}

/** 插件沙箱 K/V 持久化存储接口 */
export interface IKeyValueDB {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
  delete(key: string): Promise<void>;
}

/** 感知注入端口：插件向核心注入感知事件 */
export interface IPerceptionPort {
  /** Fire-and-forget：调用立即返回，AI 的回复通过 EventBus action.channel.reply 事件异步回传 */
  inject(event: PerceptionEvent): void;
}

/** 场景注意力上报端口：插件通知当前频道聚焦状态，并查询焦点状态 */
export interface ISceneAttentionPort {
  /**
   * 上报频道聚焦状态变更。
   * @param durationMs 可选，焦点持续时长（毫秒）；不传则使用全局 focus_duration_ms 配置。
   */
  reportSceneAttention(channelId: string, focused: boolean, durationMs?: number): void;
  /** 查询指定场景（频道）当前是否处于焦点状态 */
  isSceneFocused(channelId: string): boolean;
  /**
   * 注册来源类型的注意力策略。
   * 由插件在激活时调用，将平台特定的 sourceType → policy 映射注入内核。
   * 重复注册同一 sourceType 时后注册覆盖先注册。
   */
  registerSourcePolicies(policies: Record<string, string>): void;
}

/**
 * 视觉渲染端口：由渲染器插件（VTube Studio / Unity Bridge）实现。
 * 内核通过此端口向渲染器插件下发视觉指令。
 * 蓝图术语：提线木偶接口。
 */
export interface IVisualVesselPort {
  /** 渲染器是否已连接（WebSocket 活跃） */
  readonly isRendererConnected: boolean;
  /** 发送视觉指令到渲染器 */
  sendVisualCommand(command: VisualCommandPayload): Promise<boolean>;
}

/**
 * 插件级事件总线端口.
 * 已知系统主题（PluginEventPayloadMap 中列出的）具有完整类型推导；
 * 自定义主题（如 plugin.xxx.*）回退到 unknown。
 */
export interface IPluginEventBus {
  on<K extends keyof PluginEventPayloadMap>(
    eventName: K,
    handler: (payload: PluginEventPayloadMap[K]) => void
  ): IDisposable;
  on(eventName: string, handler: (payload: unknown) => void): IDisposable;

  emit<K extends keyof PluginEventPayloadMap>(
    eventName: K,
    payload: PluginEventPayloadMap[K]
  ): void;
  emit(eventName: string, payload: unknown): void;
}

/** 子代理注册端口 */
export interface IAgentRegistry {
  registerSubAgent(profile: SubAgentProfile): IDisposable;
}

export interface IExtensionCommandRegistry {
  registerCommand(
    commandId: string,
    handler: ExtensionCommandHandler,
    metadata?: ExtensionCommandMetadata,
  ): IDisposable;
  executeCommand(commandId: string, ...args: unknown[]): Promise<unknown>;
  listCommands(): Promise<ExtensionCommandContribution[]>;
}

// ─────────────────────────────────────────────
// 插件短期记忆
// ─────────────────────────────────────────────

/**
 * 插件短期记忆条目。
 * 存储平台特有的富消息上下文（如 @目标、回复链、消息子类型等），
 * 与 Soul 层的纯文本 ShortTermMemory 互补。
 */
export interface PluginMemoryEntry {
  /** 条目唯一 ID（由系统自动生成） */
  readonly entry_id: string;
  /** 场景 ID（如 napcat:group:123456） */
  readonly scene_id: string;
  /** 消息方向 */
  role: "inbound" | "outbound";
  /** 消息子类型（由插件自定义，如 "text" | "at" | "reply" | "image" | "poke"） */
  message_type: string;
  /** 消息文本摘要 */
  content: string;
  /** 平台特有的结构化元数据（@目标列表、回复消息 ID、表情 ID 等） */
  metadata: Record<string, unknown>;
  /** 创建时间戳（毫秒） */
  readonly timestamp: number;
}

/** 创建条目时由插件提供的字段（entry_id / timestamp 由系统填充） */
export type PluginMemoryEntryInput = Omit<PluginMemoryEntry, "entry_id" | "timestamp">;

/**
 * 插件短期记忆端口。
 * 按场景隔离，自动淘汰旧记录，支持按消息类型查询。
 * 每个插件实例拥有独立的命名空间。
 */
export interface IPluginShortTermMemory {
  /** 追加一条记忆 */
  append(entry: PluginMemoryEntryInput): Promise<PluginMemoryEntry>;
  /** 获取指定场景的最近 N 条记忆 */
  getRecent(sceneId: string, limit?: number): Promise<PluginMemoryEntry[]>;
  /** 按消息类型过滤查询 */
  getByType(sceneId: string, messageType: string, limit?: number): Promise<PluginMemoryEntry[]>;
  /** 清空指定场景的全部记忆 */
  clearScene(sceneId: string): Promise<void>;
}

// ─────────────────────────────────────────────
// 插件系统契约
// ─────────────────────────────────────────────

/** 插件沙箱上下文契约（插件实现 onActivate 时收到此对象） */
export interface ExtensionContext<TConfig = unknown> {
  readonly pluginId: string;
  readonly logger: IPluginLogger;
  readonly config: TConfig;
  readonly storage: IKeyValueDB;
  readonly shortTermMemory: IPluginShortTermMemory;
  readonly subscriptions: IDisposable[];
  readonly perception: IPerceptionPort;
  readonly sceneAttention: ISceneAttentionPort;
  readonly bus: IPluginEventBus;
  readonly agents: IAgentRegistry;
  readonly commands: IExtensionCommandRegistry;
}

/** 插件模块接口契约 */
export interface SystemPlugin<TConfig = unknown> {
  configSchema?: {
    safeParse(
      input: unknown
    ):
      | { success: true; data: TConfig }
      | {
          success: false;
          error: {
            issues?: Array<{ path?: Array<string | number>; message: string }>;
          };
        };
  };
  onActivate(ctx: ExtensionContext<TConfig>): Promise<void> | void;
  onDeactivate?(): Promise<void> | void;
}

// ─────────────────────────────────────────────
// 插件系统内置事件主题常量
// ─────────────────────────────────────────────

export const PluginSystemEventTopics = {
  ACTION_CHANNEL_REPLY: 'action.channel.reply',
  ACTION_STREAM_STARTED: 'ActionStreamStartedEvent',
  ACTION_STREAM_COMPLETED: 'ActionStreamCompletedEvent',
  ACTION_STREAM_CANCELLED: 'ActionStreamCancelledEvent',
  VISUAL_COMMAND_DISPATCH: 'VisualCommandDispatchEvent',
  PLUGIN_LOADED: 'PluginLoadedEvent',
  PLUGIN_STARTED: 'PluginStartedEvent',
  PLUGIN_STOPPED: 'PluginStoppedEvent',
  PLUGIN_ERROR: 'PluginErrorEvent',
} as const;

export type PluginSystemEventTopic =
  (typeof PluginSystemEventTopics)[keyof typeof PluginSystemEventTopics];

export type PluginScopedEventTopic<TPluginId extends string = string> =
  `plugin.${TPluginId}.${string}`;

// ─────────────────────────────────────────────
// 内置事件载荷类型
// ─────────────────────────────────────────────

/** action.channel.reply 回复指令载荷 */
export interface ChannelReplyPayload {
  /**
   * 原始感知事件 ID（即 PerceptionEvent.id）。
   * Vessel 层适配器凭此字段反查消息路由信息（trace correlation）。
   */
  traceId: string;
  /**
   * Soul 层生成的原始回复文本，可能包含情绪前缀（如 [emotion: happy]）。
   * Vessel 层负责按需清洗。
   */
  text: string;
  /** 情绪状态扩展信息，Vessel 层可按需解析（如 Live2D 动画、TTS 音色） */
  emotionState?: unknown;
}

/** 流式输出基础字段（插件事件总线级，区别于 Live2D 领域流事件） */
export interface PluginStreamBasePayload {
  channelId: string;
  /** 同一次流式生成的唯一会话 ID */
  streamId: string;
}

export interface PluginStreamStartedPayload extends PluginStreamBasePayload {}

export interface PluginStreamCompletedPayload extends PluginStreamBasePayload {
  fullText: string;
}

export interface PluginStreamCancelledPayload extends PluginStreamBasePayload {
  reason?: string;
}

/** 视觉指令载荷 — 从内核 ActionStream 翻译后分发给渲染器插件 */
export interface VisualCommandPayload {
  /** 全链路追踪 ID */
  traceId: string;
  /** 指令类型 */
  commandType: 'set_expression' | 'play_motion' | 'lip_sync' | 'set_parameter' | 'play_audio' | 'idle';
  /** Unix 毫秒时间戳 */
  timestamp: number;
  /** 表情指令 */
  expression?: { expression_id: string; blend_time_ms?: number; auto_reset?: boolean };
  /** 动作指令 */
  motion?: { motion_id: string; motion_group?: string | null; loop?: boolean; priority?: number };
  /** 口型同步 */
  lipSync?: { audio_ref?: string | null; enabled?: boolean };
  /** 参数设置 */
  parameter?: { parameters: Array<{ name: string; value: number }>; blend_time_ms?: number };
  /** 音频播放 */
  audio?: { audio_id: string; audio_data?: string | null; audio_uri?: string | null; mime_type?: string; duration_ms?: number };
  /** 情绪快照 */
  emotionState?: { emotion_type?: string; intensity?: number; trigger?: string | null };
}

/** 插件生命周期事件载荷 */
export interface PluginLifecyclePayload {
  pluginId: string;
  version?: string;
}

export interface PluginErrorPayload extends PluginLifecyclePayload {
  error: string;
}

/**
 * 已知事件主题 → 载荷类型映射表。
 * IPluginEventBus 凭此实现订阅/发布的完整类型推导；
 * 未列出的自定义主题（如 plugin.xxx.*）回退到 unknown。
 */
export interface PluginEventPayloadMap {
  'action.channel.reply': ChannelReplyPayload;
  'ActionStreamStartedEvent': PluginStreamStartedPayload;
  'ActionStreamCompletedEvent': PluginStreamCompletedPayload;
  'ActionStreamCancelledEvent': PluginStreamCancelledPayload;
  'VisualCommandDispatchEvent': VisualCommandPayload;
  'PluginLoadedEvent': PluginLifecyclePayload;
  'PluginStartedEvent': PluginLifecyclePayload;
  'PluginStoppedEvent': PluginLifecyclePayload;
  'PluginErrorEvent': PluginErrorPayload;
}
