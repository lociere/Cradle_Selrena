import { LifeClockManager } from "../../domain/organism/life-clock/life-clock-manager";
import { EmotionState } from "@cradle-selrena/protocol";
import { AIProxy } from "../../application/capabilities/inference/ai-proxy";
import { MemoryRepository } from "../../foundation/storage/repositories/memory-repository";

export class OrganismAppService {
  constructor(
    private lifeClockManager: LifeClockManager,
    private aiProxy: AIProxy,
    private memoryRepo: MemoryRepository
  ) {}

  public async getOrganismSnapshot(): Promise<{ isAwake: boolean; emotion: EmotionState; memoryCount: number }> {
    const isRunning = this.lifeClockManager.state.isRunning;
    const allMemories = this.memoryRepo.getAllMemories();
    
    return {
      isAwake: isRunning && this.aiProxy.isReady,
      emotion: {
        emotion_type: "calm",
        intensity: 0.2,
        trigger: "system_status",
        timestamp: new Date().toISOString()
      },
      memoryCount: allMemories.length 
    };
  }
}