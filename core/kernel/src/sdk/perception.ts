import { z } from 'zod';
import { Observable } from 'rxjs';

/**
 * Universal Perception DTO
 * 所有的刺激，无论是消息、视觉、还是系统心跳，都抽象为 PerceptionEvent
 */
export type SensoryType = 'VISUAL' | 'AUDITORY' | 'TEXT' | 'SYSTEM' | 'SOMATOSENSORY' | 'EMOTIONAL';

export interface PerceptionEvent {
  id: string;
  source: string; // e.g. "plugin:minecraft", "plugin:napcat"
  sensoryType: SensoryType;
  content: any; // 标准化的具体数据
  intensity?: number; // 刺激强度，直接影响生物钟模型
  timestamp: number;
}