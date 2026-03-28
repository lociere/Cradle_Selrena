/**
 * ReplyRouter — 出站消息路由器
 *
 * 职责：
 *   - 维护 eventId → 回复目标 的映射表（含 TTL 过期）
 *   - 根据路由信息将 ChannelReplyPayload 转换为 OB11 动作帧并发送
 *   - 写入出站短期记忆
 *
 * 生命周期：
 *   - register()  在 InboundPipeline 注入 PerceptionEvent 后调用，登记目标路由
 *   - sendReply() 监听 action.channel.reply 事件后调用
 *   - gc()        定期清理过期路由（由主插件每 60 秒触发）
 *   - clear()     插件停止时调用
 */

import type { ChannelReplyPayload, IPluginLogger } from '@cradle-selrena/protocol';
import type { NapcatPluginConfig } from '../../config/schema';
import { cleanOutboundReply } from '../adapters/perception-builder';
import type { ContextMemoryManager } from '../memory/context-memory-manager';

// ── 内部类型 ─────────────────────────────────────────────────────

interface ReplyTarget {
  target_type: 'group' | 'private';
  /** 群号或对方 QQ */
  target_id: string;
  /** 原始发送者 QQ（用于 @ 提及） */
  sender_id: string;
  /** 过期时间戳（毫秒） */
  expiresAt: number;
}

type OB11Segment = { type: string; data: Record<string, unknown> };

const REPLY_TARGET_TTL_MS = 5 * 60 * 1_000; // 5 分钟

// ── 路由器 ───────────────────────────────────────────────────────

export class ReplyRouter {
  private readonly _targets = new Map<string, ReplyTarget>();

  constructor(
    private readonly config: NapcatPluginConfig,
    private readonly logger: IPluginLogger,
    /** 由 WsAdapterPlugin 提供的底层发送函数 */
    private readonly sendRaw: (data: string | Buffer) => boolean,
    private readonly memoryManager: ContextMemoryManager,
  ) {}

  /**
   * 登记一条入站事件的回复路由。
   * 应在 ctx.perception.inject() 之前调用，确保 Soul 回复时路由仍存活。
   */
  register(
    eventId: string,
    target: Omit<ReplyTarget, 'expiresAt'>,
  ): void {
    this._targets.set(eventId, {
      ...target,
      expiresAt: Date.now() + REPLY_TARGET_TTL_MS,
    });
  }

  /**
   * 处理 Soul 回复事件，发送 OB11 动作帧并写入出站记忆。
   */
  async sendReply(payload: ChannelReplyPayload): Promise<void> {
    if (!this.config.reply.enabled) return;

    const eventId = String(payload.traceId);
    const routing = this._targets.get(eventId);
    if (!routing) {
      this.logger.warn(`[napcat] reply route not found, traceId=${eventId}`);
      return;
    }
    this._targets.delete(eventId);

    const replyText = cleanOutboundReply(payload.text);
    if (!replyText) return;

    const mentionSender =
      this.config.reply.mention_sender_in_group && routing.target_type === 'group';

    const message: OB11Segment[] = mentionSender
      ? [
          { type: 'at', data: { qq: routing.sender_id } },
          { type: 'text', data: { text: ' ' + replyText } },
        ]
      : [{ type: 'text', data: { text: replyText } }];

    const actionMsg =
      routing.target_type === 'group'
        ? {
            action: 'send_group_msg',
            params: { group_id: parseInt(routing.target_id, 10), message },
          }
        : {
            action: 'send_private_msg',
            params: { user_id: parseInt(routing.target_id, 10), message },
          };

    if (this.sendRaw(JSON.stringify(actionMsg))) {
      this.logger.info(
        `[napcat] reply sent -> ${routing.target_type}:${routing.target_id}`,
      );
      const sceneId =
        routing.target_type === 'group'
          ? `napcat:group:${routing.target_id}`
          : `napcat:private:${routing.target_id}`;
      await this.memoryManager.appendOutbound(sceneId, replyText);
    }
  }

  /** 清理所有已过期的路由记录（定期调用）。 */
  gc(): void {
    const now = Date.now();
    for (const [key, val] of this._targets) {
      if (val.expiresAt <= now) this._targets.delete(key);
    }
  }

  /** 清空全部路由（插件停止时调用）。 */
  clear(): void {
    this._targets.clear();
  }
}
