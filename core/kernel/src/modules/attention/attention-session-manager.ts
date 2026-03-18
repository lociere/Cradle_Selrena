import {
  ChatMessageResponse,
  createTraceContext,
  PerceptionCancelRequest,
  PerceptionMessageRequest,
  PerceptionModalityItem,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../../core/config/config-manager";
import { getLogger } from "../../core/observability/logger";
import { AIProxy } from "../ai/ai-proxy";
import { ActionStreamManager } from "../action-stream/action-stream-manager";
import { LifeClockManager } from "../life-clock/life-clock-manager";

const logger = getLogger("attention-session-manager");

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

  public static get instance(): AttentionSessionManager {
    if (!AttentionSessionManager._instance) {
      AttentionSessionManager._instance = new AttentionSessionManager();
    }
    return AttentionSessionManager._instance;
  }

  private constructor() {}

  public init(): void {
    const config = ConfigManager.instance.getConfig();
    const lifeClock = config.ai.inference.life_clock;
    this._debounceMs = lifeClock.ingress_debounce_ms;
    this._focusedDebounceMs = lifeClock.ingress_focused_debounce_ms;
    this._maxBatchMessages = lifeClock.ingress_max_batch_messages;
    this._maxBatchItems = lifeClock.ingress_max_batch_items;
    this._initialized = true;

    logger.info("注意力会话管理器初始化完成", {
      ingress_debounce_ms: this._debounceMs,
      ingress_focused_debounce_ms: this._focusedDebounceMs,
      ingress_max_batch_messages: this._maxBatchMessages,
      ingress_max_batch_items: this._maxBatchItems,
    });
  }

  public async ingest(request: PerceptionMessageRequest): Promise<ChatMessageResponse | null> {
    if (!this._initialized) {
      this.init();
    }

    const sceneId = String(request.scene_id || "default").trim() || "default";
    const state = this.getSceneState(sceneId);
    this.tryInterruptInFlight(sceneId, state);
    this.onIngressMessage(request);

    return new Promise<ChatMessageResponse | null>((resolve, reject) => {
      state.pending.push({ request, resolve, reject });
      this.scheduleFlush(sceneId, state);
    });
  }

  public stop(): void {
    for (const [sceneId, state] of this._sceneStates.entries()) {
      if (state.timer) {
        clearTimeout(state.timer);
      }
      for (const pending of state.pending) {
        pending.reject(new Error("Attention session manager stopped"));
      }
      logger.debug("注意力会话状态已清理", { scene_id: sceneId });
    }
    this._sceneStates.clear();
  }

  private getSceneState(sceneId: string): SceneIngressState {
    const existing = this._sceneStates.get(sceneId);
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
    this._sceneStates.set(sceneId, created);
    return created;
  }

  private onIngressMessage(request: PerceptionMessageRequest): void {
    const textChunks: string[] = [];
    for (const item of request.input?.items || []) {
      if (item.modality !== "text") {
        continue;
      }
      const text = String(item.text || "").trim();
      if (text) {
        textChunks.push(text);
      }
    }
    LifeClockManager.instance.onUserMessage(
      textChunks.join(" "),
      String(request.source?.source_type || "unknown"),
    );
  }

  private scheduleFlush(sceneId: string, state: SceneIngressState): void {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    const debounceMs = this.resolveDebounceMs();
    state.timer = setTimeout(() => {
      state.timer = null;
      state.chain = state.chain
        .then(() => this.flushScene(sceneId, state))
        .catch((error: unknown) => {
          logger.error("注意力场景刷新失败", {
            scene_id: sceneId,
            error: error instanceof Error ? error.message : String(error),
          });
        });
    }, debounceMs);
  }

  private tryInterruptInFlight(sceneId: string, state: SceneIngressState): void {
    if (!state.inFlightTraceId || state.cancelRequested) {
      return;
    }

    state.cancelRequested = true;
    const cancelRequest: PerceptionCancelRequest = {
      scene_id: sceneId,
      target_trace_id: state.inFlightTraceId,
      reason: "new_ingress_interrupt",
    };

    void ActionStreamManager.instance.cancelStream(sceneId, state.inFlightTraceId, "new_ingress_interrupt").catch(() => {
      // 动作流取消失败不影响主链路
    });

    void AIProxy.instance.cancelPerception(cancelRequest).catch((error: unknown) => {
      logger.warn("发送生成中断请求失败", {
        scene_id: sceneId,
        target_trace_id: state.inFlightTraceId,
        error: error instanceof Error ? error.message : String(error),
      });
    });
    logger.info("已触发生成中断请求", {
      scene_id: sceneId,
      target_trace_id: state.inFlightTraceId,
    });
  }

  private resolveDebounceMs(): number {
    const mode = LifeClockManager.instance.state.mode;
    if (mode === "focused") {
      return this._focusedDebounceMs;
    }
    return this._debounceMs;
  }

  private async flushScene(sceneId: string, state: SceneIngressState): Promise<void> {
    const queue = state.pending.splice(0, state.pending.length);
    if (queue.length === 0) {
      return;
    }

    const overflowCount = Math.max(0, queue.length - this._maxBatchMessages);
    for (const dropped of queue.slice(0, overflowCount)) {
      dropped.resolve(null);
    }

    const batch = queue.slice(overflowCount);
    const mergedRequest = this.mergeRequests(batch.map((entry) => entry.request), sceneId);
    const traceId = createTraceContext().trace_id;
    state.inFlightTraceId = traceId;
    state.cancelRequested = false;

    await ActionStreamManager.instance.startThinkingStream(
      sceneId,
      traceId,
      String(mergedRequest.source?.source_type || "unknown"),
    );

    try {
      const response = await AIProxy.instance.sendPerceptionMessage(mergedRequest, traceId);
      for (let index = 0; index < batch.length - 1; index += 1) {
        batch[index].resolve(null);
      }
      batch[batch.length - 1].resolve(response);
      logger.debug("注意力批次完成", {
        scene_id: sceneId,
        batch_size: batch.length,
        merged_item_count: mergedRequest.input.items.length,
      });
      await ActionStreamManager.instance.completeStream(
        sceneId,
        traceId,
        String(response?.emotion_state?.emotion_type || "calm"),
        String(response?.reply_content || "").length,
      );
    } catch (error) {
      for (const entry of batch) {
        entry.reject(error);
      }
      logger.error("注意力批次失败", {
        scene_id: sceneId,
        batch_size: batch.length,
        trace_id: traceId,
        error: error instanceof Error ? error.message : String(error),
      });
      await ActionStreamManager.instance.cancelStream(sceneId, traceId, "generation_failed");
    } finally {
      if (state.inFlightTraceId === traceId) {
        state.inFlightTraceId = null;
      }
      state.cancelRequested = false;
    }
  }

  private mergeRequests(requests: PerceptionMessageRequest[], sceneId: string): PerceptionMessageRequest {
    const tail = requests[requests.length - 1];
    const mergedItems: PerceptionModalityItem[] = [];

    for (const request of requests) {
      for (const item of request.input?.items || []) {
        if (mergedItems.length >= this._maxBatchItems) {
          break;
        }
        mergedItems.push(item);
      }
      if (mergedItems.length >= this._maxBatchItems) {
        break;
      }
    }

    return {
      input: {
        items: mergedItems.length > 0 ? mergedItems : tail.input.items,
      },
      scene_id: sceneId,
      familiarity: Math.max(...requests.map((item) => Number(item.familiarity || 0))),
      source: tail.source,
    };
  }
}
