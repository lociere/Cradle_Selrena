import { MemoryRepository } from "../../foundation/storage/repositories/memory-repository";
import { LongTermMemoryFragment } from "@cradle-selrena/protocol";

export class MemoryAppService {
  constructor(private memoryRepo: MemoryRepository) {}

  public async getRelevantMemories(query: string, limit?: number): Promise<LongTermMemoryFragment[]> {
    return this.memoryRepo.getRelevantMemories(query, limit);
  }

  public async addMemory(memory: Omit<LongTermMemoryFragment, "memory_id" | "timestamp">): Promise<void> {
    this.memoryRepo.addMemory(memory);
  }

  public async deleteMemory(memoryId: string): Promise<void> {
    this.memoryRepo.deleteMemory(memoryId);
  }
}