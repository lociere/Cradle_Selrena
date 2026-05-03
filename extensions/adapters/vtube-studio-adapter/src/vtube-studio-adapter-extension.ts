import WebSocket from 'ws';
import { BaseExtension } from '@cradle-selrena/extension-sdk';
import type { VisualCommandPayload } from '@cradle-selrena/protocol';
import { VTubeStudioAdapterConfig, VTubeStudioAdapterConfigSchema } from '../config/schema';

interface VTubeStudioEnvelope<TData = unknown> {
  apiName: 'VTubeStudioPublicAPI';
  apiVersion: '1.0';
  messageType: string;
  requestID?: string;
  data?: TData;
}

interface PendingRequest {
  resolve: (data: unknown) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

interface AuthenticationTokenResponse {
  authenticationToken?: string;
}

interface AuthenticationResponse {
  authenticated?: boolean;
  reason?: string;
}

export class VTubeStudioAdapterExtension extends BaseExtension<VTubeStudioAdapterConfig> {
  private _socket: WebSocket | null = null;
  private _reconnectTimer: NodeJS.Timeout | null = null;
  private _pendingRequests = new Map<string, PendingRequest>();
  private _isConnected = false;
  private _isAuthenticated = false;
  private _reconnectAttempts = 0;
  private _activeExpressionFile: string | null = null;
  private _authToken = '';

  constructor() {
    super(VTubeStudioAdapterConfigSchema);
  }

  protected override async activate(): Promise<void> {
    this._authToken = await this._resolveAuthToken();

    this.subscribe('VisualCommandDispatchEvent', (payload) => {
      void this._handleVisualCommand(payload as VisualCommandPayload);
    });

    this.registerCommand(
      'vtube-studio-adapter.status',
      async () => this._buildStatusSnapshot(),
      {
        title: 'VTube Studio Adapter Status',
        category: 'VTube Studio',
      },
    );

    this._connect();
  }

  protected override async deactivate(): Promise<void> {
    this._clearReconnectTimer();
    this._rejectPendingRequests(new Error('VTube Studio adapter stopped'));
    this._disconnect();
    this.logger.info('[vtube-studio-adapter] adapter stopped');
  }

  private _connect(): void {
    if (this._socket && this._socket.readyState === WebSocket.OPEN) {
      return;
    }

    const url = `ws://${this.config.connection.host}:${this.config.connection.port}`;
    this.logger.info('[vtube-studio-adapter] connecting', { url });

    const socket = new WebSocket(url);
    this._socket = socket;

    socket.on('open', () => {
      void this._handleOpen();
    });

    socket.on('message', (raw: WebSocket.RawData) => {
      void this._handleMessage(raw);
    });

    socket.on('close', (code: number, reason: Buffer) => {
      this.logger.warn('[vtube-studio-adapter] socket closed', {
        code,
        reason: reason.toString('utf-8'),
      });
      this._handleDisconnect();
    });

    socket.on('error', (error: Error) => {
      this.logger.warn('[vtube-studio-adapter] socket error', { error: error.message });
    });
  }

  private async _handleOpen(): Promise<void> {
    this._isConnected = true;
    this._reconnectAttempts = 0;

    try {
      await this._authenticate();
      this.logger.info('[vtube-studio-adapter] connected and authenticated');
    } catch (error) {
      this.logger.error('[vtube-studio-adapter] authentication failed', {
        error: (error as Error).message,
      });
      this._socket?.close();
    }
  }

  private async _handleMessage(raw: WebSocket.RawData): Promise<void> {
    let envelope: VTubeStudioEnvelope | null = null;
    try {
      envelope = JSON.parse(raw.toString()) as VTubeStudioEnvelope;
    } catch (error) {
      this.logger.warn('[vtube-studio-adapter] failed to parse message', {
        error: (error as Error).message,
      });
      return;
    }

    if (envelope.requestID) {
      const pending = this._pendingRequests.get(envelope.requestID);
      if (pending) {
        clearTimeout(pending.timer);
        this._pendingRequests.delete(envelope.requestID);
        pending.resolve(envelope.data ?? {});
        return;
      }
    }

    this.logger.debug('[vtube-studio-adapter] unsolicited message', {
      message_type: envelope.messageType,
    });
  }

  private _handleDisconnect(): void {
    this._isConnected = false;
    this._isAuthenticated = false;
    this._socket = null;
    this._rejectPendingRequests(new Error('VTube Studio connection closed'));
    this._scheduleReconnect();
  }

  private _disconnect(): void {
    if (this._socket) {
      this._socket.removeAllListeners();
      this._socket.close();
      this._socket = null;
    }
    this._isConnected = false;
    this._isAuthenticated = false;
  }

  private _scheduleReconnect(): void {
    if (this._reconnectTimer) {
      return;
    }

    const maxAttempts = this.config.connection.max_reconnect_attempts;
    if (maxAttempts > 0 && this._reconnectAttempts >= maxAttempts) {
      this.logger.warn('[vtube-studio-adapter] max reconnect attempts reached', {
        attempts: this._reconnectAttempts,
      });
      return;
    }

    this._reconnectAttempts += 1;
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this._connect();
    }, this.config.connection.reconnect_interval_ms);
  }

  private _clearReconnectTimer(): void {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }

  private _rejectPendingRequests(error: Error): void {
    for (const pending of this._pendingRequests.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this._pendingRequests.clear();
  }

  private async _authenticate(): Promise<void> {
    if (!this._authToken) {
      const tokenResponse = await this._sendRequest<AuthenticationTokenResponse>(
        'AuthenticationTokenRequest',
        {
          pluginName: this.config.auth.plugin_name,
          pluginDeveloper: this.config.auth.plugin_developer,
        },
      );
      this._authToken = String(tokenResponse.authenticationToken ?? '').trim();
      if (!this._authToken) {
        throw new Error('VTube Studio did not return an authentication token');
      }
      await this.ctx.storage.set('vtube-studio-auth-token', this._authToken);
    }

    const authResponse = await this._sendRequest<AuthenticationResponse>('AuthenticationRequest', {
      pluginName: this.config.auth.plugin_name,
      pluginDeveloper: this.config.auth.plugin_developer,
      authenticationToken: this._authToken,
    });

    if (!authResponse.authenticated) {
      throw new Error(authResponse.reason ?? 'authentication rejected');
    }

    this._isAuthenticated = true;
  }

  private async _resolveAuthToken(): Promise<string> {
    const configuredToken = this.config.auth.auth_token.trim();
    if (configuredToken) {
      return configuredToken;
    }

    const storedToken = await this.ctx.storage.get('vtube-studio-auth-token');
    return typeof storedToken === 'string' ? storedToken.trim() : '';
  }

  private async _handleVisualCommand(command: VisualCommandPayload): Promise<void> {
    if (!this._isAuthenticated) {
      return;
    }

    const mappingKey = this._resolveMappingKey(command);
    if (!mappingKey) {
      return;
    }

    const mapping = this._getEmotionMapping(mappingKey);
    if (!mapping) {
      this.logger.debug('[vtube-studio-adapter] no mapping for visual command', {
        mapping_key: mappingKey,
        command_type: command.commandType,
      });
      return;
    }

    if (mapping.expression_file) {
      await this._switchExpression(mapping.expression_file);
    }

    if (mapping.hotkey_id) {
      await this._sendRequest('HotkeyTriggerRequest', {
        hotkeyID: mapping.hotkey_id,
      });
    }
  }

  private _resolveMappingKey(command: VisualCommandPayload): string | null {
    const candidates = [
      command.emotionState?.emotion_type,
      command.expression?.expression_id,
      command.motion?.motion_group ?? undefined,
      command.motion?.motion_id,
      command.commandType === 'idle' ? 'neutral' : undefined,
    ].filter((value): value is string => !!value);

    for (const candidate of candidates) {
      const mapping = this._getEmotionMapping(candidate);
      if (mapping) {
        return candidate;
      }
    }

    return null;
  }

  private _getEmotionMapping(key: string): VTubeStudioAdapterConfig['emotion_mapping'][string] | null {
    const direct = this.config.emotion_mapping[key];
    if (direct) {
      return direct;
    }

    const normalizedKey = key.toLowerCase();
    for (const [mappingKey, mapping] of Object.entries(this.config.emotion_mapping)) {
      if (mappingKey.toLowerCase() === normalizedKey) {
        return mapping;
      }
    }

    return null;
  }

  private async _switchExpression(expressionFile: string): Promise<void> {
    if (this._activeExpressionFile && this._activeExpressionFile !== expressionFile) {
      await this._sendRequest('ExpressionActivationRequest', {
        expressionFile: this._activeExpressionFile,
        active: false,
      });
    }

    if (this._activeExpressionFile !== expressionFile) {
      await this._sendRequest('ExpressionActivationRequest', {
        expressionFile,
        active: true,
      });
      this._activeExpressionFile = expressionFile;
    }
  }

  private async _sendRequest<TData = unknown>(messageType: string, data: Record<string, unknown>): Promise<TData> {
    const socket = this._socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      throw new Error('VTube Studio socket is not connected');
    }

    const requestID = `vts_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const envelope: VTubeStudioEnvelope = {
      apiName: 'VTubeStudioPublicAPI',
      apiVersion: '1.0',
      messageType,
      requestID,
      data,
    };

    return new Promise<TData>((resolve, reject) => {
      const timer = setTimeout(() => {
        this._pendingRequests.delete(requestID);
        reject(new Error(`VTube Studio request timed out: ${messageType}`));
      }, 5000);

      this._pendingRequests.set(requestID, {
        resolve: (payload) => resolve(payload as TData),
        reject,
        timer,
      });

      try {
        socket.send(JSON.stringify(envelope));
      } catch (error) {
        clearTimeout(timer);
        this._pendingRequests.delete(requestID);
        reject(error as Error);
      }
    });
  }

  private _buildStatusSnapshot(): Record<string, unknown> {
    return {
      connected: this._isConnected,
      authenticated: this._isAuthenticated,
      host: this.config.connection.host,
      port: this.config.connection.port,
      reconnectAttempts: this._reconnectAttempts,
      activeExpressionFile: this._activeExpressionFile,
      mappedEmotions: Object.keys(this.config.emotion_mapping),
    };
  }
}
