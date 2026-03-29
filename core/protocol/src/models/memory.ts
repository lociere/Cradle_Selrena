// memory related types

export enum LongTermMemoryType {
  GENERAL = "general",
  PREFERENCE = "preference",
  INTERACTION = "interaction",
}

export interface LongTermMemoryFragment {
  memory_id: string;
  content: string;
  memory_type: LongTermMemoryType;
  weight: number;
  tags: string[];
  scene_id: string;
  timestamp: string;
}

export interface MemoryEntry {
  timestamp: number;
  content: string;
}
