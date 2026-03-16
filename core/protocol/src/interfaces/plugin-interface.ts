// plugin standard interface

import { ChatMessageResponse } from "../ipc/ipc-types";
import { LongTermMemoryFragment, EmotionState } from "../types";

export interface IKernelProxy {
  sendChatMessage(userInput: string, sceneId: string, familiarity?: number): Promise<ChatMessageResponse>;
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
