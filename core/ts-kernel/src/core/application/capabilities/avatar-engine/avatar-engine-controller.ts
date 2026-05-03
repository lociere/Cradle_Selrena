import { WebSocketServer, WebSocket } from 'ws';
import { EventBus } from '../../../foundation/event-bus/event-bus';
import { getLogger } from '../../../foundation/logger/logger';
import { VisualCommandDispatchEvent, ActionStreamCompletedEvent } from '@cradle-selrena/protocol';
import type {
  AvatarShellRuntimeConfig,
  VisualCommandPayload,
  ActionStreamCompletePayload,
} from '@cradle-selrena/protocol';

const logger = getLogger('avatar-engine');

export interface UnityUpstreamFrame {
  type: 'heartbeat' | 'status' | 'animation_complete' | 'error';
  data?: Record<string, unknown>;
}

export interface UnityDownstreamFrame {
  type: 'visual_command' | 'audio_push' | 'ping';
  timestamp: number;
  data?: unknown;
}

export class AvatarEngineController {
  private static _instance: AvatarEngineController | null = null;
  private _wss: WebSocketServer | null = null;
  private _clients: Set<WebSocket> = new Set();
  private _unityReady = false;
  private _heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private _lastHeartbeat = 0;
  private _initialized = false;
  private _heartbeatIntervalMs = 10000;
  private _heartbeatTimeoutMs = 30000;

  private _emotionMapping: AvatarShellRuntimeConfig['emotion_mapping'] = {
    happy: { expression_id: "happy", motion_group: "happy", animator_trigger: "happy" },
    sad: { expression_id: "sad", motion_group: "sad", animator_trigger: "sad" },
    angry: { expression_id: "angry", motion_group: "angry", animator_trigger: "angry" },
    surprised: { expression_id: "surprised", motion_group: "surprised", animator_trigger: "surprised" },
    neutral: { expression_id: "neutral", motion_group: "idle", animator_trigger: "idle" }
  };

  public static get instance(): AvatarEngineController {
    if (!AvatarEngineController._instance) {
      AvatarEngineController._instance = new AvatarEngineController();
    }
    return AvatarEngineController._instance;
  }

  private constructor() {}

  public init(config: AvatarShellRuntimeConfig): void {
    if (this._initialized) return;

    this._heartbeatIntervalMs = config.heartbeat_interval_ms;
    this._heartbeatTimeoutMs = config.heartbeat_timeout_ms;
    this._emotionMapping = config.emotion_mapping;

    this._wss = new WebSocketServer({ port: config.port });
    
    this._wss.on('connection', (ws: WebSocket) => {
      logger.info('Unity 客户端已连接');
      this._clients.add(ws);
      this._lastHeartbeat = Date.now();

      ws.on('message', (message: string) => {
        try {
          const data = JSON.parse(message);
          this._handleUpstream(data, ws);
        } catch (err) {
          logger.warn('无法解析 Unity 消息', { message });
        }
      });

      ws.on('close', () => {
        logger.warn('Unity 客户端已断开');
        this._clients.delete(ws);
        this._unityReady = false;
      });

      ws.on('error', (err) => {
        logger.error('Unity WebSocket 错误', { err });
      });
    });

    // 订阅 VisualCommandDispatchEvent
    EventBus.instance.subscribe('VisualCommandDispatchEvent', async (event) => {
      const payload = (event as VisualCommandDispatchEvent).payload;
      await this.sendVisualCommand(payload);
    });

    // 订阅 ActionStream 完毕事件，提取情绪并映射
    EventBus.instance.subscribe('ActionStreamCompletedEvent', async (event) => {
      const payload = (event as ActionStreamCompletedEvent).payload;
      await this._handleActionStreamCompleted(payload);
    });

    this._heartbeatInterval = setInterval(() => {
      if (this._clients.size > 0) {
        const pingFrame: UnityDownstreamFrame = {
          type: 'ping',
          timestamp: Date.now(),
        };
        this.broadcast(JSON.stringify(pingFrame));

        if (this._unityReady && Date.now() - this._lastHeartbeat > this._heartbeatTimeoutMs) {
          logger.warn('Unity 心跳超时，标记为未就绪');
          this._unityReady = false;
        }
      }
    }, this._heartbeatIntervalMs);

    this._initialized = true;
    logger.info('AvatarEngineController 已初始化', { port: config.port });
  }

  public stop(): void {
    if (this._heartbeatInterval) {
      clearInterval(this._heartbeatInterval);
      this._heartbeatInterval = null;
    }
    if (this._wss) {
      this._wss.close();
      this._wss = null;
    }
    this._clients.clear();
    this._unityReady = false;
    this._initialized = false;
    logger.info('AvatarEngineController 已停止');
  }

  private _handleUpstream(frame: UnityUpstreamFrame, _ws: WebSocket): void {
    if (!frame || typeof frame !== 'object' || !('type' in frame)) {
      logger.warn('Unity 发送了无效帧');
      return;
    }

    switch (frame.type) {
      case 'heartbeat':
        this._lastHeartbeat = Date.now();
        break;
      case 'status': {
        const ready = (frame.data as { ready?: boolean })?.ready ?? false;
        if (ready && !this._unityReady) {
          logger.info('Unity 渲染器已就绪');
        }
        this._unityReady = ready;
        this._lastHeartbeat = Date.now();
        break;
      }
      case 'animation_complete':
        logger.debug('Unity 动画完成', { data: frame.data });
        break;
      case 'error':
        logger.error('Unity 报告错误', { data: frame.data });
        break;
      default:
        logger.debug('Unity 未知帧类型', { type: (frame as any).type });
    }
  }

  public get isRendererConnected(): boolean {
    return this._clients.size > 0 && this._unityReady;
  }

  public async sendVisualCommand(command: VisualCommandPayload): Promise<boolean> {
    if (!this.isRendererConnected) return false;

    // 如果包含音频数据，先推送音频
    if (command.audio?.audio_data) {
      const audioFrame: UnityDownstreamFrame = {
        type: 'audio_push',
        timestamp: Date.now(),
        data: {
          audio_id: command.audio.audio_id,
          audio_data: command.audio.audio_data,
          mime_type: command.audio.mime_type ?? 'audio/wav',
          duration_ms: command.audio.duration_ms,
        },
      };
      this.broadcast(JSON.stringify(audioFrame));
    }

    // 推送视觉指令（剥离大体积音频数据）
    const visualData: VisualCommandPayload = { ...command };
    if (visualData.audio) {
      visualData.audio = { ...visualData.audio, audio_data: null as any };
    }

    const frame: UnityDownstreamFrame = {
      type: 'visual_command',
      timestamp: Date.now(),
      data: visualData,
    };
    this.broadcast(JSON.stringify(frame));
    return true;
  }

  private broadcast(data: string): void {
    for (const client of this._clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  private async _handleActionStreamCompleted(payload: ActionStreamCompletePayload): Promise<void> {
    const emotionType = payload.final_emotion;

    if (emotionType) {
      const mapping = this._emotionMapping[emotionType];
      if (mapping) {
        const cmd: VisualCommandPayload = {
          traceId: payload.stream_id || "",
          commandType: 'set_expression',
          timestamp: Date.now(),
          expression: mapping.expression_id
            ? { expression_id: mapping.expression_id }
            : undefined,
          motion: mapping.motion_group
            ? { motion_id: mapping.animator_trigger ?? emotionType, motion_group: mapping.motion_group }
            : undefined,
          emotionState: { emotion_type: emotionType },
        };
        await this.sendVisualCommand(cmd);
      }
    }
  }
}
