/**
 * ContextMemoryManager 鈥?鎻掍欢鐭湡璁板繂绠″
 *
 * 鑱岃矗锛?
 *   - 灏佽鎵€鏈夊 IExtensionShortTermMemory 鐨勮鍐欐搷浣?
 *   - 鎻愪緵缇よ亰鑳屾櫙涓婁笅鏂囨瀯寤猴紙渚?AI Core 鎰熺煡鍓嶇紑浣跨敤锛?
 *   - 鎺ㄥ娑堟伅绫诲瀷鏍囩锛堢敤浜庤蹇嗗垎绫绘绱級
 *
 * 闅旂璇存槑锛?
 *   浣跨敤 ctx.shortTermMemory (IExtensionShortTermMemory) 鍐欏叆 extension_short_term_memory 琛紝
 *   涓?AI Core 鑷韩鐨?short_term_memory 琛ㄥ畬鍏ㄩ殧绂伙紝浜掍笉褰卞搷銆?
 */

import type { IExtensionShortTermMemory, IExtensionLogger } from '@cradle-selrena/protocol';
import type { NapcatAdapterConfig } from '../../config/schema';
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
    private readonly memory: IExtensionShortTermMemory,
    private readonly config: NapcatAdapterConfig,
    private readonly logger: IExtensionLogger,
  ) {}

  // 鈹€鈹€ 娑堟伅绫诲瀷鎺ㄥ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

  // 鈹€鈹€ 鍏ョ珯璁板繂杩藉姞 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

  // 鈹€鈹€ 鍑虹珯璁板繂杩藉姞 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

  // 鈹€鈹€ 缇よ亰鑳屾櫙涓婁笅鏂囨瀯寤?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  /**
   * 璇诲彇鏈€杩?N 鏉＄兢鑱婅蹇嗭紙鍚杩囨护鐨勮儗鏅秷鎭級锛?
   * 鏍煎紡鍖栦负鍙嫾鎺ュ埌 PerceptionEvent 澶撮儴鐨勬枃鏈墠缂€銆?
   */
  async buildGroupContext(sceneId: string): Promise<string> {
    if (!this.config.memory.enabled) return '';
    const limit = this.config.memory.group_context_size;
    try {
      const recent = await this.memory.getRecent(sceneId, limit);
      if (recent.length === 0) return '';
      const lines = recent.map((e) => `  ${e.content}`).join('\n');
      return `[群聊背景上下文·最近${recent.length}条]\n${lines}`;
    } catch (err) {
      this.logger.warn('[napcat] 读取背景上下文失败', {
        scene_id: sceneId,
        error: err instanceof Error ? err.message : String(err),
      });
      return '';
    }
  }
}

