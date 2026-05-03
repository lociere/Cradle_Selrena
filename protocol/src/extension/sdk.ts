import { z } from 'zod';
import type { PerceptionEvent } from '../generated';
import type { ExtensionCommandContribution } from './extension-manifest.schema';

export type { PerceptionEvent };
export type { ExtensionCommandContribution } from './extension-manifest.schema';

export type SensoryType =
  | 'VISUAL'
  | 'AUDITORY'
  | 'TEXT'
  | 'SYSTEM'
  | 'SOMATOSENSORY'
  | 'EMOTIONAL';

export interface MCPTool<TArgs = unknown> {
  name: string;
  description: string;
  parameters: z.ZodType<TArgs>;
  handler: (args: TArgs) => Promise<unknown> | unknown;
}

export interface SubAgentProfile {
  id: string;
  name: string;
  description: string;
  tools: MCPTool[];
  memoryImpact?: boolean;
  allowInterrupt?: boolean;
}

export interface IDisposable {
  dispose(): void | Promise<void>;
}

export interface IExtensionLogger {
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

export interface IKeyValueDB {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
  delete(key: string): Promise<void>;
}

export interface IPerceptionPort {
  inject(event: PerceptionEvent): void;
}

export interface ISceneAttentionPort {
  reportSceneAttention(channelId: string, focused: boolean, durationMs?: number): void;
  isSceneFocused(channelId: string): boolean;
  registerSourcePolicies(policies: Record<string, string>): void;
}

export interface IVisualRendererPort {
  readonly isRendererConnected: boolean;
  sendVisualCommand(command: VisualCommandPayload): Promise<boolean>;
}

export interface IExtensionEventBus {
  on<K extends keyof ExtensionEventPayloadMap>(
    eventName: K,
    handler: (payload: ExtensionEventPayloadMap[K]) => void,
  ): IDisposable;
  on(eventName: string, handler: (payload: unknown) => void): IDisposable;

  emit<K extends keyof ExtensionEventPayloadMap>(
    eventName: K,
    payload: ExtensionEventPayloadMap[K],
  ): void;
  emit(eventName: string, payload: unknown): void;
}

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

export interface ExtensionMemoryEntry {
  readonly entry_id: string;
  readonly scene_id: string;
  role: 'inbound' | 'outbound';
  message_type: string;
  content: string;
  metadata: Record<string, unknown>;
  readonly timestamp: number;
}

export type ExtensionMemoryEntryInput = Omit<ExtensionMemoryEntry, 'entry_id' | 'timestamp'>;

export interface IExtensionShortTermMemory {
  append(entry: ExtensionMemoryEntryInput): Promise<ExtensionMemoryEntry>;
  getRecent(sceneId: string, limit?: number): Promise<ExtensionMemoryEntry[]>;
  getByType(sceneId: string, messageType: string, limit?: number): Promise<ExtensionMemoryEntry[]>;
  clearScene(sceneId: string): Promise<void>;
}

export interface ExtensionContext<TConfig = unknown> {
  readonly extensionId: string;
  readonly logger: IExtensionLogger;
  readonly config: TConfig;
  readonly storage: IKeyValueDB;
  readonly shortTermMemory: IExtensionShortTermMemory;
  readonly subscriptions: IDisposable[];
  readonly perception: IPerceptionPort;
  readonly sceneAttention: ISceneAttentionPort;
  readonly bus: IExtensionEventBus;
  readonly agents: IAgentRegistry;
  readonly commands: IExtensionCommandRegistry;
}

export interface SystemExtension<TConfig = unknown> {
  configSchema?: {
    safeParse(
      input: unknown,
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

export const ExtensionSystemEventTopics = {
  ACTION_CHANNEL_REPLY: 'action.channel.reply',
  ACTION_STREAM_STARTED: 'ActionStreamStartedEvent',
  ACTION_STREAM_COMPLETED: 'ActionStreamCompletedEvent',
  ACTION_STREAM_CANCELLED: 'ActionStreamCancelledEvent',
  VISUAL_COMMAND_DISPATCH: 'VisualCommandDispatchEvent',
  EXTENSION_LOADED: 'ExtensionLoadedEvent',
  EXTENSION_STARTED: 'ExtensionStartedEvent',
  EXTENSION_STOPPED: 'ExtensionStoppedEvent',
  EXTENSION_ERROR: 'ExtensionErrorEvent',
} as const;

export type ExtensionSystemEventTopic =
  (typeof ExtensionSystemEventTopics)[keyof typeof ExtensionSystemEventTopics];

export type ExtensionScopedEventTopic<TExtensionId extends string = string> =
  `extension.${TExtensionId}.${string}`;

export interface ChannelReplyPayload {
  traceId: string;
  text: string;
  emotionState?: unknown;
}

export interface ExtensionStreamBasePayload {
  channelId: string;
  streamId: string;
}

export interface ExtensionStreamStartedPayload extends ExtensionStreamBasePayload {}

export interface ExtensionStreamCompletedPayload extends ExtensionStreamBasePayload {
  fullText: string;
}

export interface ExtensionStreamCancelledPayload extends ExtensionStreamBasePayload {
  reason?: string;
}

export interface VisualCommandPayload {
  traceId: string;
  commandType: 'set_expression' | 'play_motion' | 'lip_sync' | 'set_parameter' | 'play_audio' | 'idle';
  timestamp: number;
  expression?: { expression_id: string; blend_time_ms?: number; auto_reset?: boolean };
  motion?: { motion_id: string; motion_group?: string | null; loop?: boolean; priority?: number };
  lipSync?: { audio_ref?: string | null; enabled?: boolean };
  parameter?: { parameters: Array<{ name: string; value: number }>; blend_time_ms?: number };
  audio?: { audio_id: string; audio_data?: string | null; audio_uri?: string | null; mime_type?: string; duration_ms?: number };
  emotionState?: { emotion_type?: string; intensity?: number; trigger?: string | null };
}

export interface ExtensionLifecyclePayload {
  extensionId: string;
  name?: string;
  version?: string;
}

export interface ExtensionErrorPayload extends ExtensionLifecyclePayload {
  error: string;
  stack?: string;
}

export interface ExtensionEventPayloadMap {
  'action.channel.reply': ChannelReplyPayload;
  'ActionStreamStartedEvent': ExtensionStreamStartedPayload;
  'ActionStreamCompletedEvent': ExtensionStreamCompletedPayload;
  'ActionStreamCancelledEvent': ExtensionStreamCancelledPayload;
  'VisualCommandDispatchEvent': VisualCommandPayload;
  'ExtensionLoadedEvent': ExtensionLifecyclePayload;
  'ExtensionStartedEvent': ExtensionLifecyclePayload;
  'ExtensionStoppedEvent': ExtensionLifecyclePayload;
  'ExtensionErrorEvent': ExtensionErrorPayload;
}

