/**
 * 场景注意力相关事件
 * 连接 Vessel 插件层与 Domain 生物钟层的注意力信号。
 */
import { DomainEvent } from './domain-events';
import { TraceContext } from '../core';

/**
 * 频道场景注意力变化事件
 * 由 Vessel 插件通过 IPluginHostService.reportSceneAttention 触发，
 * LifeClockManager 订阅此事件以更新有机体注意力状态。
 */
export class SceneAttentionChangedEvent extends DomainEvent {
  public readonly event_type = 'SceneAttentionChangedEvent' as const;
  public readonly channelId: string;
  public readonly focused: boolean;
  public readonly pluginId: string;
  public readonly trace_context: TraceContext;

  constructor(
    payload: { channelId: string; focused: boolean; pluginId: string },
    trace_context?: TraceContext
  ) {
    super();
    this.channelId = payload.channelId;
    this.focused = payload.focused;
    this.pluginId = payload.pluginId;
    this.trace_context = trace_context ?? { trace_id: '' };
  }
}

/**
 * 有机体注意力状态变化事件
 * 由 LifeClockManager 综合各频道注意力后发布，
 * 其他模块（如 AttentionSessionManager）订阅此事件调整行为策略。
 */
export type OrganismAttentionMode = 'ACTIVE' | 'PASSIVE' | 'IDLE';

export class OrganismAttentionChangedEvent extends DomainEvent {
  public readonly event_type = 'OrganismAttentionChangedEvent' as const;
  public readonly mode: OrganismAttentionMode;
  public readonly focusedChannels: string[];
  public readonly trace_context: TraceContext;

  constructor(
    payload: { mode: OrganismAttentionMode; focusedChannels: string[] },
    trace_context?: TraceContext
  ) {
    super();
    this.mode = payload.mode;
    this.focusedChannels = payload.focusedChannels;
    this.trace_context = trace_context ?? { trace_id: '' };
  }
}
