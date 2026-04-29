/**
 * ContextMemoryManager — 插件短期记忆管家
 *
 * 职责：
 *   - 封装所有对 IPluginShortTermMemory 的读写操作
 *   - 提供群聊背景上下文构建（供 Soul 感知前缀使用）
 *   - 推导消息类型标签（用于记忆分类检索）
 *
 * 隔离说明：
 *   使用 ctx.shortTermMemory (IPluginShortTermMemory) 写入 plugin_short_term_memory 表，
 *   与 Soul 自身的 short_term_memory 表完全隔离，互不影响。
 */

import type { IPluginShortTermMemory, IPluginLogger } from '@cradle-selrena/protocol';
import type { NapcatPluginConfig } from '../../config/schema';
import type { MessageTraits } from '../adapters/message-parser';

export interface InboundMemoryParams {
  sceneId: string;
  traits: MessageTraits;
  nickname: string;
  cleanText: string;
  senderId: string;
  isMainUser: boolean;
  replyContext: { senderId: string; senderNickname: string; previewText: string };
}

export class ContextMemoryManager {
  constructor(
    private readonly memory: IPluginShortTermMemory,
    private readonly config: NapcatPluginConfig,
    private readonly logger: IPluginLogger,
  ) {}

  // ── 消息类型推导 ─────────────────────────────────────────────

  deriveMessageType(traits: MessageTraits): string {
    if (traits.isReplyToSelf) return 'reply_self';
    if (traits.isReplyMessage) return 'reply';
    if (traits.isAtMessage) return 'at';
    if (traits.hasImage) return 'image';
    if (traits.hasVideo) return 'video';
    if (traits.hasSticker) return 'sticker';
    if (traits.hasRecord) return 'voice';
    return 'text';
  }

  // ── 入站记忆追加 ─────────────────────────────────────────────

  async appendInbound(params: InboundMemoryParams): Promise<void> {
    if (!this.config.memory.enabled) return;
    const { sceneId, traits, nickname, cleanText, senderId, isMainUser, replyContext } = params;
    try {
      await this.memory.append({
        scene_id: sceneId,
        role: 'inbound',
        message_type: this.deriveMessageType(traits),
        content: `${nickname}: ${cleanText || '[媒体消息]'}`,
        metadata: {
          sender_qq: senderId,
          sender_nickname: nickname,
          message_traits: traits,
          reply_context: replyContext.senderId ? replyContext : undefined,
          is_main_user: isMainUser,
        },
      });
    } catch (err) {
      this.logger.warn('[napcat] 短期记忆写入失败（入站）', {
        scene_id: sceneId,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  // ── 出站记忆追加 ─────────────────────────────────────────────

  async appendOutbound(sceneId: string, replyText: string): Promise<void> {
    if (!this.config.memory.enabled) return;
    try {
      await this.memory.append({
        scene_id: sceneId,
        role: 'outbound',
        message_type: 'text',
        content: `月见: ${replyText}`,
        metadata: {},
      });
    } catch (err) {
      this.logger.warn('[napcat] 短期记忆写入失败（出站）', {
        scene_id: sceneId,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  // ── 群聊背景上下文构建 ────────────────────────────────────────

  /**
   * 读取最近 N 条群聊记忆（含被过滤的背景消息），
   * 格式化为可拼接到 PerceptionEvent 头部的文本前缀。
   */
  async buildGroupContext(sceneId: string): Promise<string> {
    if (!this.config.memory.enabled) return '';
    const limit = this.config.memory.group_context_size;
    try {
      const recent = await this.memory.getRecent(sceneId, limit);
      if (recent.length === 0) return '';
      const lines = recent.map((e) => `  ${e.content}`).join('\n');
      return `[群聊背景上下文(最近${recent.length}条)]\n${lines}`;
    } catch (err) {
      this.logger.warn('[napcat] 读取背景上下文失败', {
        scene_id: sceneId,
        error: err instanceof Error ? err.message : String(err),
      });
      return '';
    }
  }
}
