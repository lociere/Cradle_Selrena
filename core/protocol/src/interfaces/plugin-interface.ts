// plugin standard interface

import {
  ASRRecognizeRequest,
  ASRRecognizeResponse,
  ChatMessageResponse,
  PerceptionMessageRequest,
  TTSSynthesizeRequest,
  TTSSynthesizeResponse,
} from "../ipc/ipc-types";
import { LongTermMemoryFragment, EmotionState } from "../types";

export type PluginLogLevel = "debug" | "info" | "warn" | "error" | "critical";

export type PluginTranscriptSceneScope = "group_scene" | "private_session" | "custom";

export interface PluginSceneTranscriptEntry {
  rootDir?: string;
  sceneScope: PluginTranscriptSceneScope;
  sceneType: "group" | "private" | "channel" | "custom";
  sceneId: string;
  identityScope?: string;
  ownerId?: string;
  ownerLabel?: string;
  summary?: string;
  role: "user" | "assistant" | "system";
  speaker: string;
  content: string;
  tags?: string[];
  occurredAt?: string;
}

export interface IKernelProxy {
  log(level: string, message: string, meta?: Record<string, unknown>): void;
  logState(level: PluginLogLevel, stateKey: string, snapshot: unknown, message: string, meta?: Record<string, unknown>): void;
  sendPerceptionMessage(request: PerceptionMessageRequest): Promise<ChatMessageResponse>;
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
