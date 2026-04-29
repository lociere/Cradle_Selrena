import { WebSocketServer, WebSocket } from 'ws';
import { EventBus } from '../../../foundation/event-bus/event-bus.js';
import { getLogger } from '../../../foundation/logger/logger.js';
import { PerceptionAppService } from '../../services/perception-app.service.js';
import { AvatarEngineController } from '../avatar-engine/avatar-engine-controller.js';
import { PerceptionEvent, ChannelReplyEvent } from '@cradle-selrena/protocol';  

const logger = getLogger('desktop-ui-engine');

export class DesktopUIController {
  private static _instance: DesktopUIController | null = null;
  private _wss: WebSocketServer | null = null;
  private _clients: Set<WebSocket> = new Set();
  private _initialized = false;
  private _perceptionAppService: PerceptionAppService | null = null;
  private _avatarStatusInterval: ReturnType<typeof setInterval> | null = null;
  private _lastAvatarShellKind: 'placeholder-puppet' | 'unity-shell' = 'placeholder-puppet';

  public static get instance(): DesktopUIController {
    if (!DesktopUIController._instance) {
      DesktopUIController._instance = new DesktopUIController();
    }
    return DesktopUIController._instance;
  }

  private constructor() {}

  public init(perceptionAppService: PerceptionAppService, port: number = 8083): void {
    if (this._initialized) return;

    this._perceptionAppService = perceptionAppService;

    this._wss = new WebSocketServer({ port });

    this._wss.on('connection', (ws: WebSocket) => {
      logger.info('Electron Desktop UI connected');
      this._clients.add(ws);
      ws.send(JSON.stringify({
        type: 'avatar_shell_status',
        shellKind: this._getAvatarShellKind(),
      }));

      ws.on('message', (message: string) => {
        try {
          const data = JSON.parse(message.toString());
          this._handleMessage(data, ws);
        } catch (err) {
          logger.warn('Failed to parse message', { message: message.toString() });
        }
      });

      ws.on('close', () => {
        logger.info('Electron Desktop UI disconnected');
        this._clients.delete(ws);
      });

      ws.on('error', (err) => {
        logger.error('Desktop UI WebSocket error', { err });
      });
    });

    EventBus.instance.subscribe('action.channel.reply', async (event: any) => {
      const reply = event as ChannelReplyEvent;
      const { traceId, text, emotionState } = reply.payload;

      if (traceId && traceId.startsWith('ui_')) {
        this.broadcast(JSON.stringify({
          type: 'chat_reply',
          text,
          emotionState
        }));
      }
    });

    this._avatarStatusInterval = setInterval(() => {
      const shellKind = this._getAvatarShellKind();
      if (shellKind !== this._lastAvatarShellKind) {
        this._lastAvatarShellKind = shellKind;
        this.broadcast(JSON.stringify({
          type: 'avatar_shell_status',
          shellKind,
        }));
      }
    }, 1500);

    this._initialized = true;
    logger.info('DesktopUIController started');
  }

  private _getAvatarShellKind(): 'placeholder-puppet' | 'unity-shell' {
    return AvatarEngineController.instance.isRendererConnected ? 'unity-shell' : 'placeholder-puppet';
  }

  private broadcast(data: string) {
    for (const client of this._clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  private _handleMessage(data: any, ws: WebSocket) {
    logger.debug('Received UI request', { type: data.type });
    if (data.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
    } else if (data.type === 'chat_input') {
      const traceId = `ui_${Date.now()}`;
      const simEvent: PerceptionEvent = {
        id: traceId,
        timestamp: Date.now(),
        source: 'desktop-ui:user',
        sensoryType: 'text',
        familiarity: 10,
        address_mode: 'direct',
        content: {
          text: data.text,
          modality: ['text']
        }
      } as PerceptionEvent;

      if (this._perceptionAppService) {
        this._perceptionAppService.processIngress(simEvent).catch((err: any) => {     
          logger.error('Failed to process UI input', { err });
        });
      } else {
        logger.warn('PerceptionAppService not initialized');
      }
    }
  }

  public stop(): void {
    if (this._avatarStatusInterval) {
      clearInterval(this._avatarStatusInterval);
      this._avatarStatusInterval = null;
    }
    if (this._wss) {
      this._wss.clients.forEach(client => client.terminate());
      this._wss.close();
      this._wss = null;
    }
    this._clients.clear();
    this._initialized = false;
    logger.info('DesktopUIController stopped');
  }
}
