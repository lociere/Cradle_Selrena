/**
 * VisualCommandDispatcher — 视觉指令分发器
 *
 * v4.5 提线木偶核心组件：将 ActionStream 事件翻译为 VisualCommand 分发事件。
 *
 * 职责：
 *   1. 监听 ActionStreamCompletedEvent，从中提取情绪状态
 *   2. 将情绪映射为具体的视觉指令（表情/动作/音频）
 *   3. 通过插件事件总线发布 VisualCommandDispatchEvent
 *   4. 渲染器插件（VTube Studio / Unity Bridge）订阅并执行
 *
 * 设计原则：
 *   - 此组件是内核 → 渲染器的唯一出口
 *   - 不直接引用任何渲染器插件实现
 *   - 通过事件解耦，支持多渲染器并行接收
 */
import {
  VisualCommandDispatchEvent,
  ActionStreamStartedEvent,
  ActionStreamCompletedEvent,
  ActionStreamCancelledEvent,
} from "@cradle-selrena/protocol";
import type {
  ActionStreamStartPayload,
  ActionStreamCompletePayload,
  ActionStreamCancelPayload,
  VisualCommandPayload,
} from "@cradle-selrena/protocol";
import { EventBus } from "../../../foundation/event-bus/event-bus";
import { getLogger } from "../../../foundation/logger/logger";

const logger = getLogger("visual-command-dispatcher");

export class VisualCommandDispatcher {
  private static _instance: VisualCommandDispatcher | null = null;
  private _initialized = false;

  public static get instance(): VisualCommandDispatcher {
    if (!VisualCommandDispatcher._instance) {
      VisualCommandDispatcher._instance = new VisualCommandDispatcher();
    }
    return VisualCommandDispatcher._instance;
  }

  private constructor() {}

  /**
   * 初始化：订阅 ActionStream 事件。
   */
  public init(): void {
    if (this._initialized) return;

    EventBus.instance.subscribe("ActionStreamStartedEvent", async (event) => {
      await this._onStreamStarted((event as ActionStreamStartedEvent).payload);
    });

    EventBus.instance.subscribe("ActionStreamCompletedEvent", async (event) => {
      await this._onStreamCompleted((event as ActionStreamCompletedEvent).payload);
    });

    EventBus.instance.subscribe("ActionStreamCancelledEvent", async (event) => {
      await this._onStreamCancelled((event as ActionStreamCancelledEvent).payload);
    });

    this._initialized = true;
    logger.info("视觉指令分发器已初始化");
  }

  /**
   * 主动发送视觉指令（供内核其他模块调用）。
   */
  public async dispatch(command: VisualCommandPayload): Promise<void> {
    await EventBus.instance.publish(new VisualCommandDispatchEvent(command, undefined));
    logger.debug("视觉指令已分发", {
      command_type: command.commandType,
      trace_id: command.traceId,
    });
  }

  // ── 事件处理 ──────────────────────────────────────────────

  private async _onStreamStarted(payload: ActionStreamStartPayload): Promise<void> {
    if (payload.stage === "thinking") {
      await this.dispatch({
        traceId: payload.stream_id ?? "",
        commandType: "set_expression",
        timestamp: Date.now(),
        expression: {
          expression_id: "thinking",
          blend_time_ms: 200,
          auto_reset: true,
        },
      });
    }
  }

  private async _onStreamCompleted(payload: ActionStreamCompletePayload): Promise<void> {
    const traceId = payload.stream_id ?? "";
    const emotion = payload.final_emotion ?? "neutral";

    // 1. 设置情绪表情
    await this.dispatch({
      traceId,
      commandType: "set_expression",
      timestamp: Date.now(),
      expression: {
        expression_id: emotion,
        blend_time_ms: 300,
        auto_reset: false,
      },
      emotionState: {
        emotion_type: emotion,
        intensity: 0.8,
      },
    });

    // 2. 延迟后回到待机（由渲染器插件自行决定是否执行）
    // 这里不做延迟，只发 idle 提示
    logger.debug("流完成，情绪表情已分发", {
      trace_id: traceId,
      emotion,
    });
  }

  private async _onStreamCancelled(payload: ActionStreamCancelPayload): Promise<void> {
    await this.dispatch({
      traceId: payload.stream_id ?? "",
      commandType: "idle",
      timestamp: Date.now(),
    });
  }

  public stop(): void {
    this._initialized = false;
    logger.info("视觉指令分发器已停止");
  }
}
