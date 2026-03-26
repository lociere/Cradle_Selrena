/**
 * 插件 SDK 核心类型
 * 定义所有插件可见的接口契约，是 Soul-Vessel 架构的公共语言。
 * 此文件不得引入任何内核实现细节（平台协议、数据库、文件系统等）。
 */
import { z } from 'zod';

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
export interface PerceptionEvent {
  id: string;
  /** 来源标识，如 "plugin:napcat", "plugin:minecraft" */
  source: string;
  sensoryType: SensoryType;
  /** 标准化的具体数据，由对应 Vessel 定义具体类型 */
  content: unknown;
  /** 刺激强度 0~1，影响生物钟模型 */
  intensity?: number;
  timestamp: number;
}

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

/** 插件沙箱 K/V 持久化存储接口 */
export interface IKeyValueDB {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
  delete(key: string): Promise<void>;
}

/** 感知注入端口：插件向核心注入感知事件 */
export interface IPerceptionPort {
  inject(event: PerceptionEvent): Promise<void>;
}

/** 场景注意力上报端口：插件通知当前频道聚焦状态 */
export interface ISceneAttentionPort {
  reportSceneAttention(channelId: string, focused: boolean): void;
}

/**
 * 插件级事件总线端口。
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

// ─────────────────────────────────────────────
// 插件系统契约
// ─────────────────────────────────────────────

/** 插件沙箱上下文契约（插件实现 onActivate 时收到此对象） */
export interface ExtensionContext<TConfig = unknown> {
  readonly pluginId: string;
  readonly logger: IPluginLogger;
  readonly config: TConfig;
  readonly storage: IKeyValueDB;
  readonly subscriptions: IDisposable[];
  readonly perception: IPerceptionPort;
  readonly sceneAttention: ISceneAttentionPort;
  readonly bus: IPluginEventBus;
  readonly agents: IAgentRegistry;
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
  ACTION_STREAM_CHUNK: 'ActionStreamChunkEvent',
  ACTION_STREAM_COMPLETED: 'ActionStreamCompletedEvent',
  ACTION_STREAM_CANCELLED: 'ActionStreamCancelledEvent',
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

export interface PluginStreamChunkPayload extends PluginStreamBasePayload {
  chunk: string;
}

export interface PluginStreamCompletedPayload extends PluginStreamBasePayload {
  fullText: string;
}

export interface PluginStreamCancelledPayload extends PluginStreamBasePayload {
  reason?: string;
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
  'ActionStreamChunkEvent': PluginStreamChunkPayload;
  'ActionStreamCompletedEvent': PluginStreamCompletedPayload;
  'ActionStreamCancelledEvent': PluginStreamCancelledPayload;
  'PluginLoadedEvent': PluginLifecyclePayload;
  'PluginStartedEvent': PluginLifecyclePayload;
  'PluginStoppedEvent': PluginLifecyclePayload;
  'PluginErrorEvent': PluginErrorPayload;
}
