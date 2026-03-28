/**
 * Plugin SDK — WsAdapterPlugin
 *
 * Abstract base class for plugins that need to host an internal WebSocket server,
 * receiving JSON-RPC style messages from external processes (e.g. NapCat, OVOS, etc.).
 *
 * Lifecycle:
 *   activate() → call startWsServer(host, port, accessToken?)
 *   deactivate() → stopWsServer() called automatically (or call super.deactivate() if overriding)
 *
 * Extension points:
 *   onJsonMessage(data)        — required, called for every valid JSON frame
 *   onRawMessage(buf)          — optional, called when JSON.parse fails (e.g. binary frames)
 *   onClientConnected(sock, req) — optional hook
 *   onClientDisconnected()    — optional hook
 *
 * Thread-safety: all callbacks run in the Node.js event loop; no extra locking needed.
 */

import type { IncomingMessage } from 'http';
import type { ZodTypeAny } from 'zod';
import { WebSocket, WebSocketServer } from 'ws';
import { BasePlugin } from './base-plugin';

type WsServerFactory = (opts: { host: string; port: number }) => WebSocketServer;

const defaultFactory: WsServerFactory = ({ host, port }) =>
  new WebSocketServer({ host, port });

export abstract class WsAdapterPlugin<TConfig = unknown> extends BasePlugin<TConfig> {
  private readonly _wsServerFactory: WsServerFactory;
  private _wss: WebSocketServer | null = null;
  private _socket: WebSocket | null = null;

  constructor(
    configSchema?: ZodTypeAny,
    wsServerFactory: WsServerFactory = defaultFactory,
  ) {
    super(configSchema);
    this._wsServerFactory = wsServerFactory;
  }

  // ── WebSocket server management ──────────────────────────────────

  /**
   * Start the WebSocket server.
   * Call this inside your `activate()` implementation.
   *
   * @param host          Bind address (e.g. '127.0.0.1')
   * @param port          Port number
   * @param accessToken   Optional shared secret — clients must send it as the
   *                      first message or via ?access_token= query parameter.
   *                      If undefined / empty, no auth is enforced.
   */
  protected startWsServer(host: string, port: number, accessToken?: string): void {
    if (this._wss) {
      this.logger.warn('WsAdapterPlugin: server already running; stopWsServer() first');
      return;
    }

    const wss = this._wsServerFactory({ host, port });
    this._wss = wss;

    wss.on('connection', (socket: WebSocket, req: IncomingMessage) => {
      // Reject if a token is configured and the request does not carry it
      if (accessToken) {
        const url = req.url ?? '';
        const params = new URLSearchParams(url.includes('?') ? url.slice(url.indexOf('?') + 1) : '');
        const provided = params.get('access_token');
        if (provided !== accessToken) {
          socket.close(1008, 'Unauthorized');
          this.logger.warn('WsAdapterPlugin: rejected connection — invalid access_token');
          return;
        }
      }

      if (this._socket) {
        this.logger.warn('WsAdapterPlugin: new client replaced existing socket');
        this._socket.close();
      }
      this._socket = socket;
      this.logger.info(`WsAdapterPlugin: client connected from ${req.socket.remoteAddress ?? 'unknown'}`);
      this.onClientConnected(socket, req);

      socket.on('message', (raw: Buffer) => {
        void this._dispatchMessage(raw);
      });

      socket.on('close', () => {
        if (this._socket === socket) this._socket = null;
        this.onClientDisconnected();
      });

      socket.on('error', (err: Error) => {
        this.logger.error('WsAdapterPlugin: socket error — ' + err.message);
      });
    });

    wss.on('error', (err: Error) => {
      this.logger.error(`WsAdapterPlugin: server error — ${err.message}`);
    });

    this.logger.info(`WsAdapterPlugin: WebSocket server started on ws://${host}:${port}`);
  }

  /** Stop the WebSocket server and close the current client socket. */
  protected stopWsServer(): void {
    if (this._socket) {
      this._socket.close();
      this._socket = null;
    }
    if (this._wss) {
      this._wss.close();
      this._wss = null;
      this.logger.info('WsAdapterPlugin: WebSocket server stopped');
    }
  }

  /**
   * Send a raw string or binary frame to the connected client.
   * Returns `true` if the data was queued; `false` if no client is connected.
   */
  protected sendRaw(data: string | Buffer): boolean {
    if (!this._socket || this._socket.readyState !== WebSocket.OPEN) return false;
    this._socket.send(data);
    return true;
  }

  /** Whether a client is currently connected and the socket is OPEN. */
  protected get isConnected(): boolean {
    return this._socket?.readyState === WebSocket.OPEN;
  }

  // ── Internal message dispatch ────────────────────────────────────

  private async _dispatchMessage(buf: Buffer): Promise<void> {
    try {
      const parsed: unknown = JSON.parse(buf.toString('utf8'));
      await Promise.resolve(this.onJsonMessage(parsed));
    } catch {
      // Not valid JSON — pass the raw buffer
      await Promise.resolve(this.onRawMessage(buf));
    }
  }

  // ── Subclass extension points ────────────────────────────────────

  /** [required] Called for every successfully parsed JSON message frame. */
  protected abstract onJsonMessage(data: unknown): Promise<void> | void;

  /** [optional] Called when a message frame cannot be parsed as JSON. */
  protected onRawMessage(_buf: Buffer): Promise<void> | void {}

  /** [optional] Called immediately after a new client establishes a connection. */
  protected onClientConnected(_socket: WebSocket, _req: IncomingMessage): void {}

  /** [optional] Called when the current client disconnects. */
  protected onClientDisconnected(): void {}

  // ── Lifecycle ────────────────────────────────────────────────────

  /**
   * Automatically stops the WebSocket server on deactivation.
   * Subclasses overriding `deactivate()` MUST call `await super.deactivate()`.
   */
  protected override async deactivate(): Promise<void> {
    this.stopWsServer();
  }
}
