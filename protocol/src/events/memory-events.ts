/**
 * Memory synchronization events between Python AI layer and Core.
 */
import { DomainEvent } from "./domain-events";
import { TraceContext } from "../core";

export interface MemorySyncPayload {
  memory: Record<string, any>;
}

export interface StateSyncPayload {
  state: Record<string, any>;
}

export interface ShortTermMemorySyncPayload {
  fragment: {
    memory_id: string;
    scene_id: string;
    role: string;
    content: string;
    importance: number;
    timestamp: string;
    trace_id?: string;
  };
}

export class MemorySyncEvent extends DomainEvent {
  public readonly event_type = "MemorySyncEvent";
  public readonly payload: MemorySyncPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: MemorySyncPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: "" };
  }
}

export class StateSyncEvent extends DomainEvent {
  public readonly event_type = "StateSyncEvent";
  public readonly payload: StateSyncPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: StateSyncPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: "" };
  }
}

export class ShortTermMemorySyncEvent extends DomainEvent {
  public readonly event_type = "ShortTermMemorySyncEvent";
  public readonly payload: ShortTermMemorySyncPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: ShortTermMemorySyncPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: "" };
  }
}

/** v4.5 记忆固化触发事件 — 由生命时钟空闲检测发布 */
export interface MemoryConsolidationPayload {
  scene_id: string;
  reason: 'idle_timeout' | 'zone_b_pressure';
}

export class MemoryConsolidationEvent extends DomainEvent {
  public readonly event_type = "MemoryConsolidationEvent";
  public readonly payload: MemoryConsolidationPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: MemoryConsolidationPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: "" };
  }
}
