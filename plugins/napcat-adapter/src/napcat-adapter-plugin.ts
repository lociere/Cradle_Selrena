/**
 * Napcat Adapter Plugin — src/napcat-adapter-plugin.ts
 *
 * 层级：Vessel — 将 OneBot 11 协议数据清洗为标准 PerceptionEvent 后注入 Soul。
 *
 * 数据流：
 *   Napcat WS → onJsonMessage() → normalizeOB11Frames() → _processEvent()
 *     → parseMessageSegments() → buildPerceptionRequest() → ctx.perception.inject()
 *   [Soul reply] → action.channel.reply → _sendReply() → Napcat WS
 */

import crypto from 'crypto';

import type { PerceptionEvent, ChannelReplyPayload } from '@cradle-selrena/protocol';
import { WsAdapterPlugin } from '@cradle-selrena/plugin-sdk';
import { NapcatPluginConfig, NapcatPluginConfigSchema } from '../config/schema';
import { parseMessageSegments } from './adapters/message-parser';
import {
  cleanInboundText,
  cleanOutboundReply,
  shouldDispatchGroupMessage,
  buildPerceptionRequest,
} from './adapters/perception-builder';
import { normalizeOB11Frames } from './adapters/ob11-normalizer';
import { SenderProfileResolver } from './adapters/profile-resolver';
import type { OB11MessageEvent } from './adapters/ob11-types';

// ─────────────────────────────────────────────────────────────────
// Internal types
// ─────────────────────────────────────────────────────────────────

interface ReplyTarget {
  target_type: 'group' | 'private';
  target_id: string;
  sender_id: string;
  expiresAt: number;
}

// reply target TTL: 5 minutes
const REPLY_TARGET_TTL_MS = 5 * 60 * 1_000;

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

/**
 * Resolve access token from config.
 * token_from_secrets=true → only from ENV, never falls back to plaintext.
 */
function resolveAccessToken(
  transport: NapcatPluginConfig['transport'],
): string {
  const envKey = String(transport.access_token_env ?? '').trim();
  if (envKey) {
    const envToken = String(process.env[envKey] ?? '').trim();
    if (envToken) return envToken;
  }
  if (transport.token_from_secrets) return '';
  return String(transport.access_token ?? '').trim();
}

// ─────────────────────────────────────────────────────────────────
// Plugin class
// ─────────────────────────────────────────────────────────────────

export class NapcatAdapterPlugin extends WsAdapterPlugin<NapcatPluginConfig> {
  private _profileResolver: SenderProfileResolver | null = null;

  /** eventId → reply routing info (with TTL) */
  private readonly _replyTargets = new Map<string, ReplyTarget>();

  /** sceneIds with active input — used for bulk focus-off on disconnect */
  private readonly _activeChannels = new Set<string>();

  constructor() {
    super(NapcatPluginConfigSchema);
  }

  // ── Lifecycle ────────────────────────────────────────────────

  protected override async activate(): Promise<void> {
    const transport = this.config.transport;
    const accessToken = resolveAccessToken(transport);

    this._profileResolver = new SenderProfileResolver(
      this.logger,
      async () => null, // callAction: relies on event.sender built-in nickname
      this.config.runtime.nickname_cache_ttl_ms,
    );

    // Periodic GC for expired reply routing records
    this.registerInterval(() => this._gcReplyTargets(), 60_000);

    this.startWsServer(transport.host, transport.port, accessToken);
    this.subscribe('action.channel.reply', (payload) => this._sendReply(payload));

    this.logger.info(
      `Napcat Adapter v0.2.0 started — ws://${transport.host}:${transport.port}`,
    );
  }

  protected override async deactivate(): Promise<void> {
    this._replyTargets.clear();
    this._activeChannels.clear();
    this._profileResolver = null;
    this.logger.info('[napcat] Napcat Adapter stopped');
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
    try {
      const normalizedEvents = normalizeOB11Frames(data);
      for (const event of normalizedEvents) {
        await this._processEvent(event as OB11MessageEvent);
      }
    } catch (err) {
      this.logger.error(
        '[napcat] message processing failed: ' +
          (err instanceof Error ? err.message : String(err)),
      );
    }
  }

  // ── Inbound pipeline ─────────────────────────────────────────

  private async _processEvent(event: OB11MessageEvent): Promise<void> {
    if ((event as Record<string, unknown>)['post_type'] !== 'message') return;

    const botSelfId = String(this.config.main_user.qq ?? '');

    if (this.config.ingress.ignore_self && String(event.user_id) === botSelfId) return;
    if (this.config.ingress.blocked_user_ids.includes(String(event.user_id))) return;
    if (
      event.message_type === 'group' &&
      this.config.ingress.blocked_group_ids.includes(String(event.group_id ?? ''))
    )
      return;
    if (event.message_type === 'private' && !this.config.ingress.private_enabled) return;
    if (event.message_type === 'group' && !this.config.ingress.group_enabled) return;

    // Cortex: parse OB11 message segments into structured data
    let parsed;
    try {
      parsed = parseMessageSegments(event, botSelfId, this.config);
    } catch (err) {
      this.logger.warn(
        '[napcat] message parse skipped: ' +
          (err instanceof Error ? err.message : String(err)),
      );
      return;
    }

    // Group dispatch policy gate
    if (
      parsed.sourceType === 'group' &&
      !shouldDispatchGroupMessage(parsed, parsed.text, this.config)
    )
      return;

    const nickname = await this._profileResolver!.resolve(event, parsed);
    const cleanText = cleanInboundText(parsed.text, event, this.config, botSelfId);

    const sceneId =
      parsed.sourceType === 'group'
        ? `napcat:group:${parsed.sourceId}`
        : `napcat:private:${parsed.senderId}`;

    const isMainUser =
      parsed.senderId !== botSelfId &&
      parsed.senderId === String(this.config.main_user.qq ?? '');

    const sessionPolicy =
      parsed.sourceType === 'group'
        ? this.config.routing.session_partition.group
        : this.config.routing.session_partition.private;

    // Cortex → Soul boundary: build standard PerceptionRequest
    const perceptionReq = buildPerceptionRequest(
      parsed,
      sceneId,
      nickname,
      cleanText,
      this.config,
      isMainUser,
      sessionPolicy,
    );
    if (!perceptionReq) return;

    const modality: string[] = ['text'];
    for (const item of parsed.mediaItems) {
      if (item.modality && !modality.includes(item.modality)) modality.push(item.modality);
    }

    const eventId = crypto.randomUUID();
    const formattedText =
      (perceptionReq.input.items[0]?.['text'] as string | undefined) ?? cleanText;

    const perceptionEvent: PerceptionEvent = {
      id: eventId,
      source: sceneId,
      sensoryType: 'TEXT',
      content: { text: formattedText, raw: perceptionReq, modality },
      timestamp: event.time ? event.time * 1000 : Date.now(),
    };

    // record reply routing with TTL
    this._replyTargets.set(eventId, {
      target_type: parsed.sourceType,
      target_id:
        parsed.sourceType === 'group' ? parsed.sourceId : parsed.senderId,
      sender_id: parsed.senderId,
      expiresAt: Date.now() + REPLY_TARGET_TTL_MS,
    });

    this.logger.debug(
      `[napcat] perception injected id=${eventId} scene=${sceneId}`,
    );

    this.ctx.sceneAttention.reportSceneAttention(sceneId, true);
    this._activeChannels.add(sceneId);

    await this.ctx.perception.inject(perceptionEvent);
  }

  // ── Outbound pipeline ─────────────────────────────────────────

  private _sendReply(payload: ChannelReplyPayload): void {
    if (!this.config.reply.enabled) return;

    const eventId = String(payload.traceId);
    const routing = this._replyTargets.get(eventId);
    if (!routing) {
      this.logger.warn(`[napcat] reply route not found, traceId=${eventId}`);
      return;
    }
    this._replyTargets.delete(eventId);

    const replyText = cleanOutboundReply(payload.text);
    if (!replyText) return;

    const mentionSender =
      this.config.reply.mention_sender_in_group && routing.target_type === 'group';

    type OB11Segment = { type: string; data: Record<string, unknown> };
    const message: OB11Segment[] = mentionSender
      ? [
          { type: 'at', data: { qq: routing.sender_id } },
          { type: 'text', data: { text: ' ' + replyText } },
        ]
      : [{ type: 'text', data: { text: replyText } }];

    const actionMsg =
      routing.target_type === 'group'
        ? { action: 'send_group_msg', params: { group_id: parseInt(routing.target_id, 10), message } }
        : { action: 'send_private_msg', params: { user_id: parseInt(routing.target_id, 10), message } };

    if (this.sendRaw(JSON.stringify(actionMsg))) {
      this.logger.info(
        `[napcat] reply sent -> ${routing.target_type}:${routing.target_id}`,
      );
    }
  }

  // ── Internal maintenance ──────────────────────────────────────

  private _gcReplyTargets(): void {
    const now = Date.now();
    for (const [key, val] of this._replyTargets) {
      if (val.expiresAt <= now) this._replyTargets.delete(key);
    }
  }
}
