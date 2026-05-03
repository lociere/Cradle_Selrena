/**
 * 鍦烘櫙娉ㄦ剰鍔涚浉鍏充簨浠?
 * 杩炴帴閫傞厤鍣ㄦ彃浠跺眰涓?Domain 鐢熺墿閽熷眰鐨勬敞鎰忓姏淇″彿銆?
 */
import { DomainEvent } from './domain-events';
import { TraceContext } from '../core';

/**
 * 棰戦亾鍦烘櫙娉ㄦ剰鍔涘彉鍖栦簨浠?
 * 鐢遍€傞厤鍣ㄦ彃浠堕€氳繃 IExtensionHostService.reportSceneAttention 瑙﹀彂锛?
 * LifeClockManager 璁㈤槄姝や簨浠朵互鏇存柊鏈夋満浣撴敞鎰忓姏鐘舵€併€?
 */
export class SceneAttentionChangedEvent extends DomainEvent {
  public readonly event_type = 'SceneAttentionChangedEvent' as const;
  public readonly channelId: string;
  public readonly focused: boolean;
  public readonly extensionId: string;
  /** 鎻掍欢鑷畾涔夌殑鐒︾偣鎸佺画鏃堕暱锛坢s锛夛紱鏈彁渚涙椂鐢?LifeClockManager 浣跨敤鍏ㄥ眬榛樿鍊?*/
  public readonly durationMs?: number;
  public readonly trace_context: TraceContext;

  constructor(
    payload: { channelId: string; focused: boolean; extensionId: string; durationMs?: number },
    trace_context?: TraceContext
  ) {
    super();
    this.channelId = payload.channelId;
    this.focused = payload.focused;
    this.extensionId = payload.extensionId;
    this.durationMs = payload.durationMs;
    this.trace_context = trace_context ?? { trace_id: '' };
  }
}

/**
 * 鏈夋満浣撴敞鎰忓姏鐘舵€佸彉鍖栦簨浠?
 * 鐢?LifeClockManager 缁煎悎鍚勯閬撴敞鎰忓姏鍚庡彂甯冿紝
 * 鍏朵粬妯″潡锛堝 AttentionSessionManager锛夎闃呮浜嬩欢璋冩暣琛屼负绛栫暐銆?
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

