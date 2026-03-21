// plugin standard interface

import {
  ASRRecognizeRequest,
  ASRRecognizeResponse,
  ChatMessageResponse,
  MessageSourceMeta,
  MessageSourceType,
  SceneRoutingHint,
  SceneSessionPolicy,
  PerceptionMessageRequest,
  TTSSynthesizeRequest,
  TTSSynthesizeResponse,
} from "../ipc/ipc-types";
import { LongTermMemoryFragment, EmotionState } from "../models";

export type PluginLogLevel = "debug" | "info" | "warn" | "error" | "critical";

export type PluginTranscriptSceneScope = "group_scene" | "private_session" | "custom";

export interface SceneRoutingRequest {
  source: MessageSourceMeta;
  routing?: SceneRoutingHint;
}

export interface SceneRoutingResult {
  scene_id: string;
  source: MessageSourceMeta;
  source_type: MessageSourceType;
  source_id: string;
  actor_id?: string;
  actor_name?: string;
  session_policy: SceneSessionPolicy;
}

export interface PluginSceneTranscriptEntry {
  root_dir?: string;
  scene_scope: PluginTranscriptSceneScope;
  scene_type: "group" | "private" | "channel" | "custom";
  transcript_scene_id: string;
  identity_scope?: string;
  owner_id?: string;
  owner_label?: string;
  summary?: string;
  role: "user" | "assistant" | "system";
  speaker: string;
  content: string;
  tags?: string[];
  occurred_at?: string;
}

export interface IKernelProxy {
  log(level: string, message: string, meta?: Record<string, unknown>): void;
  logState(level: PluginLogLevel, stateKey: string, snapshot: unknown, message: string, meta?: Record<string, unknown>): void;
  resolveScene(request: SceneRoutingRequest): Promise<SceneRoutingResult>;
  submitChannelMessage(request: PerceptionMessageRequest): Promise<ChatMessageResponse | null>;
  synthesizeSpeech(request: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse>;
  recognizeSpeech(request: ASRRecognizeRequest): Promise<ASRRecognizeResponse>;
  appendSceneTranscript(entry: PluginSceneTranscriptEntry): Promise<void>;
  getRelevantMemories(query: string, limit?: number): Promise<LongTermMemoryFragment[]>;
  addMemory(memory: Omit<LongTermMemoryFragment, "memory_id" | "timestamp">): Promise<void>;
  deleteMemory(memoryId: string): Promise<void>;
  getSelfConfig(): Promise<Record<string, any>>;
  updateSelfConfig(config: Record<string, any>): Promise<void>;
  getGlobalConfig(): Promise<Record<string, any>>;
  getCurrentState(): Promise<{ isAwake: boolean; emotion: EmotionState; memoryCount: number }>;
  subscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void>;
  unsubscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void>;
}

export interface IBasePlugin {
  kernelProxy?: IKernelProxy;
  preLoad?(): Promise<void>;
  onInit(): Promise<void>;
  onStart(): Promise<void>;
  onStop?(): Promise<void>;
  onDestroy?(): Promise<void>;
}
