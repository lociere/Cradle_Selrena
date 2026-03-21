import {
  ActionStreamCancelledEvent,
  ActionStreamChunkEvent,
  ActionStreamCompletedEvent,
  ActionStreamStartedEvent,
  ActionFramePayload,
  createTraceContext,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../../../infrastructure/config/config-manager";
import { EventBus } from "../../../infrastructure/event-bus/event-bus";
import { getLogger } from "../../../infrastructure/logger/logger";

const logger = getLogger("action-stream-manager");

type StreamState = {
  sceneId: string;
  streamId: string;
  sourceType: string;
  sequence: number;
  emittedChunks: number;
  timer: NodeJS.Timeout | null;
};

export class ActionStreamManager {
  private static _instance: ActionStreamManager | null = null;
  private _initialized: boolean = false;
  private _enabled: boolean = true;
  private _channel: "live2d" = "live2d";
  private _chunkIntervalMs: number = 80;
  private _maxChunksPerStream: number = 120;
  private _emitThinkingChunks: boolean = true;
  private _emitEmotionOnComplete: boolean = true;
  private readonly _streams: Map<string, StreamState> = new Map();

  public static get instance(): ActionStreamManager {
    if (!ActionStreamManager._instance) {
      ActionStreamManager._instance = new ActionStreamManager();
    }
    return ActionStreamManager._instance;
  }

  private constructor() {}

  public init(): void {
    const config = ConfigManager.instance.getConfig();
    const streamConfig = config.ai.inference.action_stream;
    this._enabled = streamConfig.enabled;
    this._channel = streamConfig.channel;
    this._chunkIntervalMs = streamConfig.chunk_interval_ms;
    this._maxChunksPerStream = streamConfig.max_chunks_per_stream;
    this._emitThinkingChunks = streamConfig.emit_thinking_chunks;
    this._emitEmotionOnComplete = streamConfig.emit_emotion_on_complete;
    this._initialized = true;

    logger.info("动作流管理器初始化完成", {
      enabled: this._enabled,
      channel: this._channel,
      chunk_interval_ms: this._chunkIntervalMs,
      max_chunks_per_stream: this._maxChunksPerStream,
      emit_thinking_chunks: this._emitThinkingChunks,
      emit_emotion_on_complete: this._emitEmotionOnComplete,
    });
  }

  public async startThinkingStream(sceneId: string, streamId: string, sourceType: string): Promise<void> {
    if (!this.ensureReady()) {
      return;
    }

    const existing = this._streams.get(streamId);
    if (existing) {
      this.clearStream(streamId, existing);
    }

    const state: StreamState = {
      sceneId,
      streamId,
      sourceType,
      sequence: 0,
      emittedChunks: 0,
      timer: null,
    };
    this._streams.set(streamId, state);

    await EventBus.instance.publish(
      new ActionStreamStartedEvent(
        {
          scene_id: sceneId,
          stream_id: streamId,
          channel: this._channel,
          source_type: sourceType,
          stage: "thinking",
        },
        createTraceContext({ trace_id: streamId }),
      )
    );

    if (!this._emitThinkingChunks) {
      return;
    }

    state.timer = setInterval(() => {
      void this.emitThinkingChunk(state);
    }, this._chunkIntervalMs);
  }

  public async completeStream(sceneId: string, streamId: string, finalEmotion: string, replyLength: number): Promise<void> {
    if (!this.ensureReady()) {
      return;
    }

    const state = this._streams.get(streamId);
    if (state) {
      this.clearStream(streamId, state);
    }

    if (this._emitEmotionOnComplete) {
      await EventBus.instance.publish(
        new ActionStreamChunkEvent(
          {
            scene_id: sceneId,
            stream_id: streamId,
            channel: this._channel,
            sequence: (state?.sequence || 0) + 1,
            stage: "ending",
            frame: this.buildEmotionFrame(finalEmotion),
          },
          createTraceContext({ trace_id: streamId }),
        )
      );
    }

    await EventBus.instance.publish(
      new ActionStreamCompletedEvent(
        {
          scene_id: sceneId,
          stream_id: streamId,
          channel: this._channel,
          final_emotion: finalEmotion,
          reply_length: replyLength,
        },
        createTraceContext({ trace_id: streamId }),
      )
    );
  }

  public async cancelStream(sceneId: string, streamId: string, reason: string): Promise<void> {
    if (!this.ensureReady()) {
      return;
    }

    const state = this._streams.get(streamId);
    if (state) {
      this.clearStream(streamId, state);
    }

    await EventBus.instance.publish(
      new ActionStreamCancelledEvent(
        {
          scene_id: sceneId,
          stream_id: streamId,
          channel: this._channel,
          reason,
        },
        createTraceContext({ trace_id: streamId }),
      )
    );
  }

  public stop(): void {
    for (const [streamId, state] of this._streams.entries()) {
      this.clearStream(streamId, state);
    }
    this._streams.clear();
  }

  private ensureReady(): boolean {
    if (!this._initialized) {
      this.init();
    }
    return this._enabled;
  }

  private clearStream(streamId: string, state: StreamState): void {
    if (state.timer) {
      clearInterval(state.timer);
    }
    this._streams.delete(streamId);
  }

  private async emitThinkingChunk(state: StreamState): Promise<void> {
    if (!this._streams.has(state.streamId)) {
      return;
    }

    if (state.emittedChunks >= this._maxChunksPerStream) {
      await this.cancelStream(state.sceneId, state.streamId, "max_chunks_reached");
      return;
    }

    state.sequence += 1;
    state.emittedChunks += 1;

    await EventBus.instance.publish(
      new ActionStreamChunkEvent(
        {
          scene_id: state.sceneId,
          stream_id: state.streamId,
          channel: this._channel,
          sequence: state.sequence,
          stage: "thinking",
          frame: this.buildThinkingFrame(state.sequence),
        },
        createTraceContext({ trace_id: state.streamId }),
      )
    );
  }

  private buildThinkingFrame(sequence: number): ActionFramePayload {
    const pattern = sequence % 4;
    if (pattern === 0) {
      return {
        action_type: "gaze",
        value: "left",
        intensity: 0.25,
        duration_ms: this._chunkIntervalMs,
      };
    }
    if (pattern === 1) {
      return {
        action_type: "gaze",
        value: "right",
        intensity: 0.25,
        duration_ms: this._chunkIntervalMs,
      };
    }
    if (pattern === 2) {
      return {
        action_type: "motion",
        value: "idle_breath",
        intensity: 0.2,
        duration_ms: this._chunkIntervalMs,
      };
    }
    return {
      action_type: "expression",
      value: "focus",
      intensity: 0.3,
      duration_ms: this._chunkIntervalMs,
    };
  }

  private buildEmotionFrame(emotion: string): ActionFramePayload {
    const normalized = String(emotion || "calm").toLowerCase();
    if (normalized.includes("happy") || normalized.includes("开心")) {
      return { action_type: "expression", value: "smile", intensity: 0.7, duration_ms: 300 };
    }
    if (normalized.includes("angry") || normalized.includes("生气")) {
      return { action_type: "expression", value: "angry", intensity: 0.7, duration_ms: 300 };
    }
    if (normalized.includes("sad") || normalized.includes("难过")) {
      return { action_type: "expression", value: "sad", intensity: 0.6, duration_ms: 300 };
    }
    if (normalized.includes("shy") || normalized.includes("害羞")) {
      return { action_type: "expression", value: "shy", intensity: 0.55, duration_ms: 300 };
    }
    return { action_type: "expression", value: "calm", intensity: 0.35, duration_ms: 280 };
  }
}
