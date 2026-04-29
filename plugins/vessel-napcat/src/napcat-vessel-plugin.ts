/**
 * Napcat Vessel Plugin — src/napcat-vessel-plugin.ts
 *
 * 层级：Vessel — 将 OneBot 11 协议数据清洗为标准 PerceptionEvent 后注入 Soul。
 *
 * 数据流：
 *   Napcat WS → onJsonMessage()
 *     → normalizeOB11Frames() → InboundPipeline.process() → ctx.perception.inject()
 *   [Soul reply] → action.channel.reply → ReplyRouter.sendReply() → Napcat WS
 *
 * 模块结构：
 *   inbound/inbound-pipeline.ts   — 入站消息处理（过滤、解析、感知注入）
 *   outbound/reply-router.ts      — 出站回复路由与发送
 *   memory/context-memory-manager.ts — 插件短期记忆读写（与 Soul 本体 STM 隔离）
 *   adapters/                     — OB11 协议适配层（Cortex）
 */

import type { ChannelReplyPayload } from '@cradle-selrena/protocol';
import { WsAdapterPlugin } from '@cradle-selrena/plugin-sdk';
import { NapcatPluginConfig, NapcatPluginConfigSchema } from '../config/schema';
import { normalizeOB11Frames } from './adapters/ob11-normalizer';
import { SenderProfileResolver } from './adapters/profile-resolver';
import type { OB11MessageEvent } from './adapters/ob11-types';
import { ContextMemoryManager } from './memory/context-memory-manager';
import { ReplyRouter } from './outbound/reply-router';
import { InboundPipeline } from './inbound/inbound-pipeline';

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

/**
 * 从配置解析 access token。
 * token_from_secrets=true → 仅从 ENV 读取，不回退到明文。
 */
function resolveAccessToken(transport: NapcatPluginConfig['transport']): string {
  const envKey = String(transport.access_token_env ?? '').trim();
  if (envKey) {
    const envToken = String(process.env[envKey] ?? '').trim();
    if (envToken) return envToken;
  }
  if (transport.token_from_secrets) return '';
  return String(transport.access_token ?? '').trim();
}

/** NapCat action 请求超时（ms） */
const ACTION_TIMEOUT_MS = 5_000;

interface PendingCall {
  resolve: (data: unknown) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
}

// ─────────────────────────────────────────────────────────────────
// Plugin class（生命周期编排，不含业务逻辑）
// ─────────────────────────────────────────────────────────────────

export class NapcatVesselPlugin extends WsAdapterPlugin<NapcatPluginConfig> {
  private _pipeline: InboundPipeline | null = null;
  private _router: ReplyRouter | null = null;

  /** 持有活跃场景 ID 的集合，断连时用于批量关闭注意力 */
  private readonly _activeChannels = new Set<string>();

  /** 等待 NapCat action echo 响应的暂挂调用表 */
  private readonly _pendingCalls = new Map<string, PendingCall>();

  constructor() {
    super(NapcatPluginConfigSchema);
  }

  // ── Lifecycle ────────────────────────────────────────────────

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

    // 将插件配置的注意力策略注入内核 LifeClockManager
    this.ctx.sceneAttention.registerSourcePolicies(
      this.config.ingress.source_focus_policies,
    );

    this.logger.info(
      `Napcat Vessel v0.3.0 started — ws://${transport.host}:${transport.port}`,
    );
  }

  protected override async deactivate(): Promise<void> {
    // 清除所有暂挂调用，避免断连后泄漏 Promise
    for (const [, pending] of this._pendingCalls) {
      clearTimeout(pending.timer);
      pending.reject(new Error('plugin deactivated'));
    }
    this._pendingCalls.clear();
    this._router?.clear();
    this._activeChannels.clear();
    this._pipeline = null;
    this._router = null;
    this.logger.info('[napcat] Napcat Vessel stopped');
    await super.deactivate(); // closes WS server
  }

  // ── WsAdapterPlugin overrides ────────────────────────────────

  protected override onClientDisconnected(): void {
    for (const channelId of this._activeChannels) {
      this.ctx.sceneAttention.reportSceneAttention(channelId, false);
    }
    this._activeChannels.clear();
  }

  protected override async onJsonMessage(data: unknown): Promise<void> {
    // 优先检查 echo 帧（NapCat action 响应），避免误入消息管道
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
   * 对 NapCat 发起 action 请求并等待 echo 响应。
   * OB11 协议：{"action":"","params":{},"echo":"<id>"} → {"echo":"<id>","retcode":0,"data":{...}}
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