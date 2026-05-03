/**
 * ReplyRouter 鈥?鍑虹珯娑堟伅璺敱鍣?
 *
 * 鑱岃矗锛?
 *   - 缁存姢 eventId 鈫?鍥炲鐩爣 鐨勬槧灏勮〃锛堝惈 TTL 杩囨湡锛?
 *   - 鏍规嵁璺敱淇℃伅灏?ChannelReplyPayload 杞崲涓?OB11 鍔ㄤ綔甯у苟鍙戦€?
 *   - 鍐欏叆鍑虹珯鐭湡璁板繂
 *
 * 鐢熷懡鍛ㄦ湡锛?
 *   - register()  鍦?InboundPipeline 娉ㄥ叆 PerceptionEvent 鍚庤皟鐢紝鐧昏鐩爣璺敱
 *   - sendReply() 鐩戝惉 action.channel.reply 浜嬩欢鍚庤皟鐢?
 *   - gc()        瀹氭湡娓呯悊杩囨湡璺敱锛堢敱涓绘彃浠舵瘡 60 绉掕Е鍙戯級
 *   - clear()     鎻掍欢鍋滄鏃惰皟鐢?
 */

import type { ChannelReplyPayload, IExtensionLogger, ISceneAttentionPort } from '@cradle-selrena/protocol';
import type { NapcatAdapterConfig } from '../../config/schema';
import { cleanOutboundReply } from '../adapters/perception-builder';
import type { ContextMemoryManager } from '../memory/context-memory-manager';

// 鈹€鈹€ 鍐呴儴绫诲瀷 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

interface ReplyTarget {
  target_type: 'group' | 'private';
  /** 缇ゅ彿鎴栧鏂?QQ */
  target_id: string;
  /** 鍘熷鍙戦€佽€?QQ锛堢敤浜?@ 鎻愬強锛?*/
  sender_id: string;
  /** 杩囨湡鏃堕棿鎴筹紙姣锛?*/
  expiresAt: number;
}

type OB11Segment = { type: string; data: Record<string, unknown> };

const REPLY_TARGET_TTL_MS = 5 * 60 * 1_000; // 5 鍒嗛挓

// 鈹€鈹€ 璺敱鍣?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export class ReplyRouter {
  private readonly _targets = new Map<string, ReplyTarget>();

  constructor(
    private readonly config: NapcatAdapterConfig,
    private readonly logger: IExtensionLogger,
    /** 鐢?WsAdapterExtension 鎻愪緵鐨勫簳灞傚彂閫佸嚱鏁?*/
    private readonly sendRaw: (data: string | Buffer) => boolean,
    private readonly memoryManager: ContextMemoryManager,
    /**
     * 鍥炲鍙戦€佹垚鍔熷悗鐢ㄤ簬缁湡鐒︾偣璁℃椂鍣ㄣ€?
     * 纭繚鐢ㄦ埛鍦ㄦ敹鍒板洖澶嶅悗浠嶆湁瀹屾暣鐨勭劍鐐圭獥鍙ｇ户缁璇濄€?
     */
    private readonly sceneAttention: ISceneAttentionPort,
  ) {}

  /**
   * 鐧昏涓€鏉″叆绔欎簨浠剁殑鍥炲璺敱銆?
  * 搴斿湪 ctx.perception.inject() 涔嬪墠璋冪敤锛岀‘淇?AI Core 鍥炲鏃惰矾鐢变粛瀛樻椿銆?
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
  * 澶勭悊 AI Core 鍥炲浜嬩欢锛屽彂閫?OB11 鍔ㄤ綔甯у苟鍐欏叆鍑虹珯璁板繂銆?
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
      // 鍥炲鍙戝嚭鍚庣画鏈熺劍鐐癸細缁欑敤鎴蜂竴涓畬鏁寸殑鏂拌秴鏃剁獥鍙ｇ户缁璇濓紝
      // 閬垮厤鍥?AI 鎬濊€冭€楁椂瀵艰嚧鏈夋晥绐楀彛澶у箙缂╂按銆?
      this.sceneAttention.reportSceneAttention(
        sceneId,
        true,
        this.config.ingress.focus_duration_ms,
      );
      await this.memoryManager.appendOutbound(sceneId, replyText);
    }
  }

  /** 娓呯悊鎵€鏈夊凡杩囨湡鐨勮矾鐢辫褰曪紙瀹氭湡璋冪敤锛夈€?*/
  gc(): void {
    const now = Date.now();
    for (const [key, val] of this._targets) {
      if (val.expiresAt <= now) this._targets.delete(key);
    }
  }

  /** 娓呯┖鍏ㄩ儴璺敱锛堟彃浠跺仠姝㈡椂璋冪敤锛夈€?*/
  clear(): void {
    this._targets.clear();
  }
}

