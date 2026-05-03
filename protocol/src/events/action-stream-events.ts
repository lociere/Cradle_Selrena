import { DomainEvent } from "./domain-events";
import { TraceContext } from "../core";
import type { VisualCommandPayload } from "../extension/sdk";

export interface ActionStreamBasePayload {
  scene_id: string;
  stream_id: string;
  channel: "live2d";
}

export interface ActionStreamStartPayload extends ActionStreamBasePayload {
  source_type: string;
  stage: "thinking" | "speaking";
}

export interface ActionStreamCompletePayload extends ActionStreamBasePayload {
  final_emotion: string;
  reply_length: number;
}

export interface ActionStreamCancelPayload extends ActionStreamBasePayload {
  reason: string;
}

export class ActionStreamStartedEvent extends DomainEvent {
  public readonly event_type = "ActionStreamStartedEvent";
  public readonly payload: ActionStreamStartPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: ActionStreamStartPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: payload.stream_id };
  }
}

export class ActionStreamCompletedEvent extends DomainEvent {
  public readonly event_type = "ActionStreamCompletedEvent";
  public readonly payload: ActionStreamCompletePayload;
  public readonly trace_context: TraceContext;

  constructor(payload: ActionStreamCompletePayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: payload.stream_id };
  }
}

export class ActionStreamCancelledEvent extends DomainEvent {
  public readonly event_type = "ActionStreamCancelledEvent";
  public readonly payload: ActionStreamCancelPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: ActionStreamCancelPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: payload.stream_id };
  }
}

/**
 * 瑙嗚鎸囦护鍒嗗彂浜嬩欢銆?
 * 浠庡唴鏍?ActionStream 缈昏瘧鍚庡彂甯冿紝鐢辨覆鏌撳櫒鎻掍欢锛圴Tube Studio / Unity Bridge锛夎闃呮墽琛屻€?
 * 钃濆浘鏈锛氭彁绾挎湪鍋舵寚浠ゃ€?
 */
export class VisualCommandDispatchEvent extends DomainEvent {
  public readonly event_type = "VisualCommandDispatchEvent";
  public readonly payload: VisualCommandPayload;
  public readonly trace_context: TraceContext;

  constructor(payload: VisualCommandPayload, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: payload.traceId };
  }
}
