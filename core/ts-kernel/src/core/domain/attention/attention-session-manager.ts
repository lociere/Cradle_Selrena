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

/**
 * 被中断的 in-flight 批次内容快照。
 * 不携带 Promise 回调，仅保留语义内容供下次合并。
 * address_mode 也需保存：若被打断批次是 direct 呼唤，恢复后仍应以 direct 优先级合并。
 */
type InterruptedContent = {
  text?: string;
  items?: NonNullable<PerceptionMessageRequest['content']['items']>;
  modality: string[];
  address_mode: 'direct' | 'ambient';
};

type SceneIngressState = {
  pending: PendingIngress[];
  timer: NodeJS.Timeout | null;
  chain: Promise<void>;
  inFlightTraceId: string | null;
  cancelRequested: boolean;
  /**
   * 被中断的 in-flight 批次的合并内容，供下一次 flush 时前置拼入。
   * 确保中断后 AI 收到的是「被打断消息 + 新消息」的完整上下文。
   * 级联中断下会持续累积：A 被中断 → interruptedContent=A；
   * A+B 被中断 → interruptedContent=merge(A,B)，最终 AI 看到完整链。
   */
  interruptedContent: InterruptedContent | null;
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
    const lifeClock = config.persona.inference.life_clock;
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
      interruptedContent: null,
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

    // 提取并清空上次被中断的内容快照，作为本次合并的前缀。
    // 在构造 mergedRequest 之前置空，避免异常路径重复使用。
    const prefix = state.interruptedContent;
    state.interruptedContent = null;

    const mergedRequest = this.mergeRequests(batch.map((entry) => entry.request), prefix);
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
      if (state.cancelRequested) {
        // 本次 in-flight 是被后续消息中断的（不是真实错误）。
        // 保存合并内容（已含 prefix + 本批次）供下次 flush 前置拼入，
        // 确保 AI 最终收到「所有未回复消息 + 新消息」的完整上下文。
        state.interruptedContent = {
          text: mergedRequest.content?.text,
          items: mergedRequest.content?.items ? [...mergedRequest.content.items] : undefined,
          modality: mergedRequest.content?.modality ? [...mergedRequest.content.modality] : [],
          address_mode: mergedRequest.address_mode,
        };
        // 优雅结束，不向上层抛错——这些消息内容已被保存，会在下次 flush 中处理
        for (const entry of batch) {
          entry.resolve(null);
        }
        logger.info('in-flight 批次被中断，内容已暂存供下次合并', {
          scene_id: source,
          batch_size: batch.length,
          trace_id: traceId,
        });
      } else {
        for (const entry of batch) {
          entry.reject(error);
        }
        logger.error('注意力批次失败', {
          scene_id: source,
          batch_size: batch.length,
          trace_id: traceId,
          error: error instanceof Error ? error.message : String(error),
        });
      }
      await this._actionStream.cancelStream(source, traceId, state.cancelRequested ? 'interrupted' : 'generation_failed');
    } finally {
      if (state.inFlightTraceId === traceId) {
        state.inFlightTraceId = null;
      }
      state.cancelRequested = false;
    }
  }

  private mergeRequests(
    requests: PerceptionMessageRequest[],
    prefix?: InterruptedContent | null,
  ): PerceptionMessageRequest {
    const tail = requests[requests.length - 1];

    const modalities = new Set<string>(prefix?.modality ?? []);
    const allItems: NonNullable<PerceptionMessageRequest['content']['items']> = [
      ...(prefix?.items ?? []),
    ];

    const textParts: string[] = [];
    if (prefix?.text) textParts.push(prefix.text);

    for (const r of requests) {
      if (r.content?.text) textParts.push(r.content.text);
      r.content?.modality?.forEach(m => modalities.add(m));
      if (r.content?.items) allItems.push(...r.content.items);
    }

    // items 总数超出上限时保留最新的
    const trimmedItems =
      allItems.length > this._maxBatchItems
        ? allItems.slice(allItems.length - this._maxBatchItems)
        : allItems;

    return {
      id: tail.id,
      sensoryType: tail.sensoryType,
      source: tail.source,
      timestamp: tail.timestamp,
      familiarity: tail.familiarity,
      // 被中断的前缀或当前批次中任一消息是 direct 呼唤，则合并结果为 direct
      address_mode: (prefix?.address_mode === 'direct' || requests.some(r => r.address_mode === 'direct'))
        ? 'direct'
        : 'ambient',
      content: {
        text: textParts.join('\n') || undefined,
        modality: Array.from(modalities),
        items: trimmedItems.length > 0 ? trimmedItems : undefined,
      },
    };
  }
}
