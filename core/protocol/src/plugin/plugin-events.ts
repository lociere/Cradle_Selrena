/**
 * 插件生命周期相关事件
 */
import { DomainEvent } from "../events/domain-events";
import { TraceContext } from "../core";
import type { ChannelReplyPayload } from "./sdk";

export interface PluginEventPayload {
  [key: string]: unknown;
}

export abstract class PluginEvent extends DomainEvent {
  public readonly event_type: string;
  public readonly payload: unknown;
  public readonly trace_context: TraceContext;

  constructor(event_type: string, payload: unknown = {}, trace_context?: TraceContext, occurredAt?: number) {
    super(occurredAt);
    this.event_type = event_type;
    this.payload = payload;
    this.trace_context = trace_context ?? { trace_id: "" };
  }
}

export class PluginLoadedEvent extends PluginEvent {
  constructor(payload: PluginEventPayload = {}, trace_context?: TraceContext) {
    super("PluginLoadedEvent", payload, trace_context);
  }
}

export class PluginStartedEvent extends PluginEvent {
  constructor(payload: PluginEventPayload = {}, trace_context?: TraceContext) {
    super("PluginStartedEvent", payload, trace_context);
  }
}

export class PluginStoppedEvent extends PluginEvent {
  constructor(payload: PluginEventPayload = {}, trace_context?: TraceContext) {
    super("PluginStoppedEvent", payload, trace_context);
  }
}

export class PluginUnloadedEvent extends PluginEvent {
  constructor(payload: PluginEventPayload = {}, trace_context?: TraceContext) {
    super("PluginUnloadedEvent", payload, trace_context);
  }
}

export class PluginErrorEvent extends PluginEvent {
  constructor(payload: PluginEventPayload = {}, trace_context?: TraceContext) {
    super("PluginErrorEvent", payload, trace_context);
  }
}

/**
 * Soul 层向 Vessel 层下发回复指令的领域事件。
 * 通过全局 EventBus 发布，Vessel 适配器订阅后执行出站发送。
 */
export class ChannelReplyEvent extends PluginEvent {
  declare readonly payload: ChannelReplyPayload;

  constructor(payload: ChannelReplyPayload, trace_context?: TraceContext) {
    super("action.channel.reply", payload, trace_context);
  }
}
