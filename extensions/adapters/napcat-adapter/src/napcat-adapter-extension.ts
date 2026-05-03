/**
 * NapCat adapter extension.
 *
 * Responsibility:
 * - receive OneBot 11 frames from NapCat
 * - normalize them into standard perception input
 * - route channel replies back to NapCat
 */

import type { ChannelReplyPayload } from '@cradle-selrena/protocol';
import { WsAdapterExtension } from '@cradle-selrena/extension-sdk';
import { NapcatAdapterConfig, NapcatAdapterConfigSchema } from '../config/schema';
import { normalizeOB11Frames } from './adapters/ob11-normalizer';
import { SenderProfileResolver } from './adapters/profile-resolver';
import type { OB11MessageEvent } from './adapters/ob11-types';
import { ContextMemoryManager } from './memory/context-memory-manager';
import { ReplyRouter } from './outbound/reply-router';
import { InboundPipeline } from './inbound/inbound-pipeline';

// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
// Helpers
// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

/**
 * 浠庨厤缃В鏋?access token銆?
 * token_from_secrets=true 鈫?浠呬粠 ENV 璇诲彇锛屼笉鍥為€€鍒版槑鏂囥€?
 */
function resolveAccessToken(transport: NapcatAdapterConfig['transport']): string {
  const envKey = String(transport.access_token_env ?? '').trim();
  if (envKey) {
    const envToken = String(process.env[envKey] ?? '').trim();
    if (envToken) return envToken;
  }
  if (transport.token_from_secrets) return '';
  return String(transport.access_token ?? '').trim();
}

/** NapCat action 璇锋眰瓒呮椂锛坢s锛?*/
const ACTION_TIMEOUT_MS = 5_000;

interface PendingCall {
  resolve: (data: unknown) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
}

// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
// Extension lifecycle coordinator; domain logic stays in the pipeline modules.
// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export class NapcatAdapterExtension extends WsAdapterExtension<NapcatAdapterConfig> {
  private _pipeline: InboundPipeline | null = null;
  private _router: ReplyRouter | null = null;

  /** 鎸佹湁娲昏穬鍦烘櫙 ID 鐨勯泦鍚堬紝鏂繛鏃剁敤浜庢壒閲忓叧闂敞鎰忓姏 */
  private readonly _activeChannels = new Set<string>();

  /** 绛夊緟 NapCat action echo 鍝嶅簲鐨勬殏鎸傝皟鐢ㄨ〃 */
  private readonly _pendingCalls = new Map<string, PendingCall>();

  constructor() {
    super(NapcatAdapterConfigSchema);
  }

  // 鈹€鈹€ Lifecycle 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  protected override async activate(): Promise<void> {
    const transport = this.config.transport;
    const accessToken = resolveAccessToken(transport);

    const profileResolver = new SenderProfileResolver(
      this.logger,
      (action, params) => this._callAction(action, params),
      this.config.runtime.nickname_cache_ttl_ms,
    );

    const memoryManager = new ContextMemoryManager(
      this.ctx.shortTermMemory,
      this.config,
      this.logger,
    );

    this._router = new ReplyRouter(
      this.config,
      this.logger,
      (data) => this.sendRaw(data),
      memoryManager,
      this.ctx.sceneAttention,
    );

    this._pipeline = new InboundPipeline(
      this.config,
      this.logger,
      this.ctx.perception,
      this.ctx.sceneAttention,
      this._activeChannels,
      this._router,
      profileResolver,
      memoryManager,
      (action, params) => this._callAction(action, params),
    );

    this.registerInterval(() => this._router!.gc(), 60_000);
    this.startWsServer(transport.host, transport.port, accessToken);
    this.subscribe('action.channel.reply', (payload) =>
      this._router!.sendReply(payload as ChannelReplyPayload),
    );

    // 灏嗘彃浠堕厤缃殑娉ㄦ剰鍔涚瓥鐣ユ敞鍏ュ唴鏍?LifeClockManager
    this.ctx.sceneAttention.registerSourcePolicies(
      this.config.ingress.source_focus_policies,
    );

    this.logger.info(
      `NapCat Adapter v0.3.0 started 鈥?ws://${transport.host}:${transport.port}`,
    );
  }

  protected override async deactivate(): Promise<void> {
    // 娓呴櫎鎵€鏈夋殏鎸傝皟鐢紝閬垮厤鏂繛鍚庢硠婕?Promise
    for (const [, pending] of this._pendingCalls) {
      clearTimeout(pending.timer);
      pending.reject(new Error('extension deactivated'));
    }
    this._pendingCalls.clear();
    this._router?.clear();
    this._activeChannels.clear();
    this._pipeline = null;
    this._router = null;
    this.logger.info('[napcat-adapter] NapCat Adapter stopped');
    await super.deactivate(); // closes WS server
  }

  // 鈹€鈹€ WsAdapterExtension overrides 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  protected override onClientDisconnected(): void {
    for (const channelId of this._activeChannels) {
      this.ctx.sceneAttention.reportSceneAttention(channelId, false);
    }
    this._activeChannels.clear();
  }

  protected override async onJsonMessage(data: unknown): Promise<void> {
    // 浼樺厛妫€鏌?echo 甯э紙NapCat action 鍝嶅簲锛夛紝閬垮厤璇叆娑堟伅绠￠亾
    if (data && typeof data === 'object' && 'echo' in data) {
      const frame = data as Record<string, unknown>;
      const echo = String(frame['echo'] ?? '');
      const pending = this._pendingCalls.get(echo);
      if (pending) {
        clearTimeout(pending.timer);
        this._pendingCalls.delete(echo);
        const retcode = Number(frame['retcode'] ?? frame['ret_code'] ?? 0);
        if (retcode !== 0) {
          pending.reject(new Error(`NapCat action failed: retcode=${retcode}`));
        } else {
          pending.resolve(frame['data'] ?? null);
        }
        return;
      }
    }

    if (!this._pipeline) return;
    try {
      const normalizedEvents = normalizeOB11Frames(data);
      for (const event of normalizedEvents) {
        await this._pipeline.process(event as OB11MessageEvent);
      }
    } catch (err) {
      this.logger.error(
        '[napcat] message processing failed: ' +
          (err instanceof Error ? err.message : String(err)),
        { stack: err instanceof Error ? err.stack : undefined },
      );
    }
  }

  /**
   * 瀵?NapCat 鍙戣捣 action 璇锋眰骞剁瓑寰?echo 鍝嶅簲銆?
   * OB11 鍗忚锛歿"action":"","params":{},"echo":"<id>"} 鈫?{"echo":"<id>","retcode":0,"data":{...}}
   */
  private _callAction(action: string, params: Record<string, unknown>): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const echo = `${action}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      const timer = setTimeout(() => {
        this._pendingCalls.delete(echo);
        reject(new Error(`NapCat action timeout: ${action}`));
      }, ACTION_TIMEOUT_MS);
      this._pendingCalls.set(echo, { resolve, reject, timer });
      const sent = this.sendRaw(JSON.stringify({ action, params, echo }));
      if (!sent) {
        clearTimeout(timer);
        this._pendingCalls.delete(echo);
        reject(new Error('NapCat WS not connected'));
      }
    });
  }
}
