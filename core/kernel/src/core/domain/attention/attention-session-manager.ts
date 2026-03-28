import { ChatMessageResponse, createTraceContext, IAICapabilityPort, IActionStreamPort, PerceptionCancelRequest, PerceptionMessageRequest } from '@cradle-selrena/protocol';
import { ConfigManager } from '../../foundation/config/config-manager';
import { getLogger } from '../../foundation/logger/logger';
import { LifeClockManager } from '../organism/life-clock/life-clock-manager';

const logger = getLogger('attention-session-manager');

type PendingIngress = {
  request: PerceptionMessageRequest;
  resolve: (value: ChatMessageResponse | null) => void;
  reject: (reason?: unknown) => void;
};

type SceneIngressState = {
  pending: PendingIngress[];
  timer: NodeJS.Timeout | null;
  chain: Promise<void>;
  inFlightTraceId: string | null;
  cancelRequested: boolean;
};

export class AttentionSessionManager {
  private static _instance: AttentionSessionManager | null = null;
  private readonly _sceneStates: Map<string, SceneIngressState> = new Map();
  private _initialized: boolean = false;
  private _debounceMs: number = 1400;
  private _focusedDebounceMs: number = 700;
  private _maxBatchMessages: number = 4;
  private _maxBatchItems: number = 24;
  private _aiProxy!: IAICapabilityPort;
  private _actionStream!: IActionStreamPort;

  public static get instance(): AttentionSessionManager {
    if (!AttentionSessionManager._instance) {
      AttentionSessionManager._instance = new AttentionSessionManager();
    }
    return AttentionSessionManager._instance;
  }

  private constructor() {}

  public init(aiProxy: IAICapabilityPort, actionStream: IActionStreamPort): void {
    this._aiProxy = aiProxy;
    this._actionStream = actionStream;
    const config = ConfigManager.instance.getConfig();
    const lifeClock = config.ai.inference.life_clock;
    this._debounceMs = lifeClock.ingress_debounce_ms;
    this._focusedDebounceMs = lifeClock.ingress_focused_debounce_ms;
    this._maxBatchMessages = lifeClock.ingress_max_batch_messages;
    this._maxBatchItems = lifeClock.ingress_max_batch_items;
    this._initialized = true;

    logger.info('注意力会话管理器初始化完成', {
      ingress_debounce_ms: this._debounceMs,
      ingress_focused_debounce_ms: this._focusedDebounceMs,
      ingress_max_batch_messages: this._maxBatchMessages,
      ingress_max_batch_items: this._maxBatchItems,
    });
  }

  public async ingest(request: PerceptionMessageRequest): Promise<ChatMessageResponse | null> {
    if (!this._initialized) {
      throw new Error('AttentionSessionManager 未初始化，请先调用 init()');
    }

    const source = String(request.source || 'default').trim() || 'default';
    const state = this.getSceneState(source);
    this.tryInterruptInFlight(source, state);

    return new Promise<ChatMessageResponse | null>((resolve, reject) => {
      state.pending.push({ request, resolve, reject });
      this.scheduleFlush(source, state);
    });
  }

  public async stop(): Promise<void> {
    // 先取消所有定时器和拒绝所有待处理请求
    for (const [source, state] of this._sceneStates.entries()) {
      if (state.timer) {
        clearTimeout(state.timer);
      }
      for (const pending of state.pending) {
        pending.reject(new Error('Attention session manager stopped'));
      }
      logger.debug('注意力会话状态已清理', { scene_id: source });
    }
    // 等待所有 in-flight 的 flushScene 链完成
    const chains = Array.from(this._sceneStates.values()).map((s) => s.chain);
    await Promise.allSettled(chains);
    this._sceneStates.clear();
  }

  private getSceneState(source: string): SceneIngressState {
    const existing = this._sceneStates.get(source);
    if (existing) {
      return existing;
    }

    const created: SceneIngressState = {
      pending: [],
      timer: null,
      chain: Promise.resolve(),
      inFlightTraceId: null,
      cancelRequested: false,
    };
    this._sceneStates.set(source, created);
    return created;
  }

  private scheduleFlush(source: string, state: SceneIngressState): void {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    const debounceMs = this.resolveDebounceMs();
    state.timer = setTimeout(() => {
      state.timer = null;
      state.chain = state.chain
        .then(() => this.flushScene(source, state))
        .catch((error: unknown) => {
          logger.error('注意力场景刷新失败', {
            scene_id: source,
            error: error instanceof Error ? error.message : String(error),
          });
        });
    }, debounceMs);
  }

  private tryInterruptInFlight(source: string, state: SceneIngressState): void {
    if (!state.inFlightTraceId || state.cancelRequested) {
      return;
    }

    state.cancelRequested = true;
    const cancelRequest: PerceptionCancelRequest = {
      scene_id: source,
      target_trace_id: state.inFlightTraceId,
      reason: 'new_ingress_interrupt',
    };

    void this._actionStream.cancelStream(source, state.inFlightTraceId, 'new_ingress_interrupt').catch(() => {});

    void this._aiProxy.cancelPerception(cancelRequest).catch((error: unknown) => {
      logger.warn('发送生成中断请求失败', {
        scene_id: source,
        target_trace_id: state.inFlightTraceId,
        error: error instanceof Error ? error.message : String(error),
      });
    });
    logger.info('已触发生成中断请求', {
      scene_id: source,
      target_trace_id: state.inFlightTraceId,
    });
  }

  private resolveDebounceMs(): number {
    const mode = LifeClockManager.instance.state.mode;
    if (mode === 'focused') {
      return this._focusedDebounceMs;
    }
    return this._debounceMs;
  }

  private async flushScene(source: string, state: SceneIngressState): Promise<void> {
    const queue = state.pending.splice(0, state.pending.length);
    if (queue.length === 0) {
      return;
    }

    const overflowCount = Math.max(0, queue.length - this._maxBatchMessages);
    for (const dropped of queue.slice(0, overflowCount)) {
      dropped.resolve(null);
    }

    const batch = queue.slice(overflowCount);
    const mergedRequest = this.mergeRequests(batch.map((entry) => entry.request), source);
    const traceId = createTraceContext().trace_id;
    state.inFlightTraceId = traceId;
    state.cancelRequested = false;

    await this._actionStream.startThinkingStream(
      source,
      traceId,
      String(mergedRequest.source || 'unknown'),
    );

    try {
      const response = await this._aiProxy.sendPerceptionMessage(mergedRequest, traceId);
      for (let index = 0; index < batch.length - 1; index += 1) {
        batch[index].resolve(null);
      }
      batch[batch.length - 1].resolve(response);
      logger.debug('注意力批次完成', {
        scene_id: source,
        batch_size: batch.length,
      });
      await this._actionStream.completeStream(
        source,
        traceId,
        String(response?.emotion_state?.emotion_type || 'calm'),
        String(response?.reply_content || '').length,
      );
    } catch (error) {
      for (const entry of batch) {
        entry.reject(error);
      }
      logger.error('注意力批次失败', {
        scene_id: source,
        batch_size: batch.length,
        trace_id: traceId,
        error: error instanceof Error ? error.message : String(error),
      });
      await this._actionStream.cancelStream(source, traceId, 'generation_failed');
    } finally {
      if (state.inFlightTraceId === traceId) {
        state.inFlightTraceId = null;
      }
      state.cancelRequested = false;
    }
  }

  private mergeRequests(requests: PerceptionMessageRequest[], source: string): PerceptionMessageRequest {  
    const tail = requests[requests.length - 1];
    
    const texts = requests.map(r => r.content?.text).filter(Boolean);
    const mergedText = texts.join(' ');
    const modalities = new Set<string>();
    const allItems: NonNullable<PerceptionMessageRequest['content']['items']> = [];
    for (const r of requests) {
      r.content?.modality?.forEach(m => modalities.add(m));
      if (r.content?.items) {
        allItems.push(...r.content.items);
      }
    }

    return {
      id: tail.id,
      sensoryType: tail.sensoryType,
      source: tail.source,
      timestamp: tail.timestamp,
      familiarity: tail.familiarity,
      content: {
        text: mergedText || undefined,
        modality: Array.from(modalities),
        items: allItems.length > 0 ? allItems : undefined,
      }
    };
  }
}
