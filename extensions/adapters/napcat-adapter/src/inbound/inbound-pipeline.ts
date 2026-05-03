/**
 * InboundPipeline 鈥?鍏ョ珯娑堟伅澶勭悊绠￠亾
 *
 * 鑱岃矗锛?
 *   - 鎺ユ敹宸插綊涓€鍖栫殑 OB11MessageEvent锛屾墽琛?Cortex 灞傚鐞?
 *   - 鍩虹杩囨护锛坕gnore_self / blocked / enabled锛?
 *   - 瑙ｆ瀽娑堟伅娈?鈫?鏋勫缓 PerceptionEvent 鈫?娉ㄥ叆 AI Core
 *   - 鍐欏叆鎻掍欢鐭湡璁板繂锛堝惈琚繃婊ょ殑鑳屾櫙娑堟伅锛?
 *
 * 灞傜骇璇存槑锛?
 *   姝ゆā鍧楀睘浜?Adapter 褰掍竴鍖栧眰锛岃礋璐ｅ皢 OB11 鍗忚鏁版嵁娓呮礂涓烘爣鍑嗘牸寮忋€?
 *   鍚?AI Core 浼犻€掔殑 PerceptionEvent.content 浠呭惈璇箟鏁版嵁锛屼笉鍚换浣曞钩鍙扮鏈夊瓧娈点€?
 *   鍏ョ珯闃叉姢锛堥€熺巼闄愬埗/鐔旀柇锛夌敱鍐呮牳 PerceptionAppService 閫忔槑澶勭悊锛屾彃浠舵棤闇€鎰熺煡銆?
 */

import crypto from 'crypto';

import type {
  PerceptionEvent,
  PerceptionModalityItem,
  IExtensionLogger,
  IPerceptionPort,
  ISceneAttentionPort,
} from '@cradle-selrena/protocol';
import type { NapcatAdapterConfig } from '../../config/schema';
import { parseMessageSegments, type ParsedMessage, type ReplyContext } from '../adapters/message-parser';
import {
  cleanInboundText,
  buildPerceptionRequest,
} from '../adapters/perception-builder';
import { SenderProfileResolver } from '../adapters/profile-resolver';
import type { OB11MessageEvent } from '../adapters/ob11-types';
import type { ReplyRouter } from '../outbound/reply-router';
import type { ContextMemoryManager } from '../memory/context-memory-manager';

export class InboundPipeline {

  constructor(
    private readonly config: NapcatAdapterConfig,
    private readonly logger: IExtensionLogger,
    private readonly perception: IPerceptionPort,
    private readonly sceneAttention: ISceneAttentionPort,
    /** 鐢变富鎻掍欢鎸佹湁骞跺湪鏂繛鏃舵竻绌猴紝姝ゅ鍏变韩寮曠敤 */
    private readonly activeChannels: Set<string>,
    private readonly router: ReplyRouter,
    private readonly profileResolver: SenderProfileResolver,
    private readonly memoryManager: ContextMemoryManager,
    /** NapCat action 璋冪敤锛堢敤浜?get_msg銆乬et_group_member_info 绛夛級 */
    private readonly callAction: (action: string, params: Record<string, unknown>) => Promise<unknown>,
  ) {}

  /**
   * 澶勭悊鍗曟潯 OB11 浜嬩欢銆?
   * 闈?message 绫诲瀷鐨勫抚锛堝績璺炽€乴ifecycle 绛夛級鐩存帴闈欓粯涓㈠純銆?
   */
  async process(event: OB11MessageEvent): Promise<void> {
    if ((event as Record<string, unknown>)['post_type'] !== 'message') return;

    this.logger.debug('[napcat] 鏀跺埌娑堟伅浜嬩欢', {
      message_type: event.message_type,
      user_id: event.user_id,
      group_id: event.group_id,
    });

    // self_id = 鏈哄櫒浜鸿嚜宸辩殑 QQ 鍙凤紙鏉ヨ嚜 OB11 浜嬩欢鏈韩锛夛紝鐢ㄤ簬杩囨护鑷彂娑堟伅
    const botSelfId = String(event.self_id ?? '');
    // main_user.qq = 鏈哄櫒浜轰富浜虹殑 QQ 鍙凤紝鐢ㄤ簬 isMainUser 鏍囪锛堜笌杩囨护鏃犲叧锛?
    const mainUserQq = String(this.config.main_user.qq ?? '');

    // 鈹€鈹€ 鍩虹杩囨护 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    if (this.config.ingress.ignore_self && String(event.user_id) === botSelfId) return;
    if (this.config.ingress.blocked_user_ids.includes(String(event.user_id))) return;
    if (
      event.message_type === 'group' &&
      this.config.ingress.blocked_group_ids.includes(String(event.group_id ?? ''))
    )
      return;
    if (event.message_type === 'private' && !this.config.ingress.private_enabled) return;
    if (event.message_type === 'group' && !this.config.ingress.group_enabled) return;

    // 鈹€鈹€ Cortex锛氳В鏋?OB11 娑堟伅娈?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    let parsed: ParsedMessage;
    try {
      parsed = parseMessageSegments(event, botSelfId, this.config);
    } catch (err) {
      this.logger.warn(
        '[napcat] message parse skipped: ' +
          (err instanceof Error ? err.message : String(err)),
      );
      return;
    }

    // reply 娈典粎鎼哄甫娑堟伅 ID锛岄€氳繃 get_msg 寮傛琛ュ叏 sender 鍜屽唴瀹规憳瑕?
    if (parsed.replyMessageId && !parsed.replyContext.senderId) {
      const enrichedCtx = await this._fetchReplyContext(parsed.replyMessageId);
      if (enrichedCtx) parsed = { ...parsed, replyContext: enrichedCtx };
    }

    const nickname = await this.profileResolver.resolve(event, parsed);
    const cleanText = cleanInboundText(parsed.text, event, this.config, botSelfId);

    const mediaDesc = parsed.mediaItems.length > 0
      ? parsed.mediaItems.map(i => {
          const kind = i.metadata?.['visual_kind'] ? `/${String(i.metadata['visual_kind'])}` : '';
          return `${i.modality}${kind}`;
        }).join(',')
      : undefined;
    const activeTraits = Object.entries(parsed.messageTraits)
      .filter(([, v]) => v === true)
      .map(([k]) => k)
      .join(',') || undefined;

    this.logger.info('[napcat] 鏀跺埌娑堟伅', {
      scene: parsed.sourceType === 'group'
        ? `缇?{parsed.sourceId}${event['group_name'] ? `(${String(event['group_name'])})` : ''}`
        : `绉佽亰:${parsed.senderId}`,
      nickname,
      text: parsed.text.slice(0, 80) || '(绌?',
      media: mediaDesc,
      traits: activeTraits,
    });

    const sceneId =
      parsed.sourceType === 'group'
        ? `napcat:group:${parsed.sourceId}`
        : `napcat:private:${parsed.senderId}`;

    const isMainUser =
      parsed.senderId !== botSelfId &&
      mainUserQq !== '' &&
      parsed.senderId === mainUserQq;

    const memParams = {
      sceneId,
      traits: parsed.messageTraits,
      nickname,
      cleanText,
      senderId: parsed.senderId,
      isMainUser,
      replyContext: parsed.replyContext,
    };

    // 鈹€鈹€ 娉ㄦ剰鍔涚瓥鐣ラ棬鎺э紙绾悓姝ワ紝鏈€鍏堟墽琛岋紝閬垮厤闈炵劍鐐规湡娑堟伅瑙﹀彂鏄傝吹鐨勫紓姝ヨ皟鐢級鈹€鈹€
    // sourceFocusPolicy 鐢?napcat 鎻掍欢鍦ㄦ縺娲绘椂閫氳繃 registerSourcePolicies 娉ㄥ叆鍐呮牳锛?
    // 姝ゅ浠庨€傞厤鍣ㄩ厤缃腑璇诲彇瀵瑰簲鏉ユ簮绫诲瀷鐨勭瓥鐣ワ紝涓庡唴鏍哥姸鎬佷繚鎸佷竴鑷淬€?
    const sourceFocusPolicy =
      ((this.config.ingress.source_focus_policies ?? {}) as Record<string, string>)[
        parsed.sourceType
      ] ?? 'always_focused';

    // 鍞ら啋璇嶆娴嬶細浠呯湅娑堟伅鍐呭鏈韩锛園鏈哄櫒浜?鎴?鍖呭惈 wake_words 鍏抽敭璇嶏級銆?
    // isMainUser 涓嶅弬涓庢澶勫垽鏂€斺€斾富鐢ㄦ埛鐨勭壒娈婂搷搴斾紭鍏堢骇鐢?source_focus_policies 閰嶇疆
    // 鎺у埗锛堝绉佽亰閰嶇疆涓?always_focused锛夛紝涓嶅湪浠ｇ爜涓‖缂栫爜锛屼繚鎸佺瓥鐣ヤ笌閫昏緫鍒嗙銆?
    // 浣跨敤 parsed.text 鑰岄潪 cleanText锛屽洜涓?strip_leading_wake_words 鍙兘宸插皢
    // 寮€澶寸殑鍞ら啋璇嶅墺绂伙紝浼氬鑷存娴嬪け璐ャ€?
    const containsWakeWord =
      parsed.messageTraits.isAtMessage ||
      this.config.ingress.wake_words.some((w: string) => w && parsed.text.includes(w));

    // 璇诲彇鍐呮牳褰撳墠缁存姢鐨勯閬撶劍鐐圭姸鎬侊紙鐢?LifeClockManager 鐨?per-channel 璁℃椂鍣ㄧ鐞嗭級
    const currentlyFocused = this.sceneAttention.isSceneFocused(sceneId);

    const shouldInject =
      sourceFocusPolicy === 'always_focused' ||
      sourceFocusPolicy === 'chat_or_wake_focus_with_timeout' ||
      (sourceFocusPolicy === 'wake_word_focus' && containsWakeWord) ||
      (
        sourceFocusPolicy === 'wake_word_focus_with_timeout' &&
        (containsWakeWord || currentlyFocused)
      );

    if (!shouldInject) {
      // 闈炵劍鐐规湡娑堟伅锛氬啓鍏ヨ儗鏅蹇嗕緵涓嬫缇よ亰涓婁笅鏂囦娇鐢紝涓嶈Е鍙?AI 灞?
      await this.memoryManager.appendInbound(memParams);
      return;
    }

    // 鈹€鈹€ 閫氳繃闂ㄦ帶鍚庯細鎵ц鑰楁椂鎿嶄綔骞舵瀯寤烘劅鐭ヤ簨浠?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    // 浠讳綍閫氳繃鐒︾偣闂ㄦ帶鐨勬秷鎭兘缁湡涓嶆椿璺冭秴鏃剁獥鍙ｃ€?
    // 杩欑‘淇濊秴鏃朵粠"鏈€鍚庝竴娆℃椿鍔?锛堣€岄潪鍞ら啋璇嶈Е鍙戞椂鍒伙級寮€濮嬭绠楋紝
    // 閬垮厤鐢ㄦ埛鍦ㄧ瓑寰?AI 鍥炲鏃剁劍鐐圭獥鍙ｆ倓鐒惰€楀敖銆?
    // 鍦?inject 涔嬪墠閫氱煡鍐呮牳锛岀‘淇?AI Core 鏋侀€熷搷搴旀椂鐒︾偣鐘舵€佸凡灏辩华銆?
    this.sceneAttention.reportSceneAttention(
      sceneId,
      true,
      this.config.ingress.focus_duration_ms,
    );

    const familiarity =
      parsed.sourceType === 'group'
        ? Number(this.config.ingress.familiarity.group ?? 0)
        : Number(this.config.ingress.familiarity.private ?? 0);

    const sessionPolicy =
      parsed.sourceType === 'group'
        ? this.config.routing.session_partition.group
        : this.config.routing.session_partition.private;

    const cortexOutput = buildPerceptionRequest(
      parsed,
      sceneId,
      nickname,
      cleanText,
      this.config,
      isMainUser,
      sessionPolicy,
    );
    if (!cortexOutput) return;

    // 缇よ亰鑳屾櫙涓婁笅鏂囷細浠呭湪娉ㄥ叆鏃舵墠寮傛鎷夊彇锛岄伩鍏嶉潪鐒︾偣娑堟伅瑙﹀彂鏃犵敤 IO
    const contextPrefix =
      parsed.sourceType === 'group'
        ? await this.memoryManager.buildGroupContext(sceneId)
        : '';
    const finalText = contextPrefix
      ? `${contextPrefix}\n${cortexOutput.formattedText}`
      : cortexOutput.formattedText;

    const modality: string[] = ['text'];
    for (const item of parsed.mediaItems) {
      if (item.modality && !modality.includes(item.modality)) modality.push(item.modality);
    }

    const eventId = crypto.randomUUID();

    // address_mode锛欰dapter 褰掍竴鍖栧眰灏嗗钩鍙颁俊鍙疯浆鎹负璇箟瀵诲潃妯″紡锛屽睆钄藉钩鍙扮粏鑺傘€?
    // always_focused锛堢鑱婏級鎴栧惈鍞ら啋璇?鈫?direct锛堟湀瑙佽鏄庣‘鍛煎敜锛岄鏈熷洖澶嶏級
    // 鐒︾偣绐楀彛鍐呯殑鏅€氱兢鑱婃秷鎭?鈫?ambient锛堟湀瑙佸彲鑷富鍐冲畾鏄惁寮€鍙ｏ級
    const addressMode: 'direct' | 'ambient' =
      sourceFocusPolicy === 'always_focused' || containsWakeWord
        ? 'direct'
        : 'ambient';

    // PerceptionEvent.content 涓ユ牸鍙惡甯﹁涔夋暟鎹紝鏃犱换浣曢€傞厤鍣ㄧ鏈夊瓧娈?
    const perceptionEvent: PerceptionEvent = {
      id: eventId,
      source: sceneId,
      sensoryType: 'TEXT',
      familiarity,
      address_mode: addressMode,
      content: {
        text: finalText,
        modality,
        items: cortexOutput.inputItems as PerceptionModalityItem[],
      },
      timestamp: event.time ? event.time * 1000 : Date.now(),
    };

    // 鐧昏鍥炲璺敱锛堝繀椤诲湪 inject 涔嬪墠锛岄伩鍏?AI Core 鏋侀€熷洖澶嶆椂鎵句笉鍒拌矾鐢憋級
    this.router.register(eventId, {
      target_type: parsed.sourceType,
      target_id: parsed.sourceType === 'group' ? parsed.sourceId : parsed.senderId,
      sender_id: parsed.senderId,
    });

    this.activeChannels.add(sceneId);
    this.perception.inject(perceptionEvent);

    // 鍐欏叆鎻掍欢鐭湡璁板繂锛堟寜 scene_id 鑷姩闅旂锛氱鑱婃瘡鐢ㄦ埛銆佺兢鑱婃瘡缇わ級
    await this.memoryManager.appendInbound(memParams);
  }

  /**
   * 閫氳繃 NapCat get_msg API 琛ュ叏琚紩鐢ㄦ秷鎭殑鍙戦€佽€呭拰鍐呭鎽樿銆?
   * 浠呭湪 reply 娈靛彧鏈?ID锛堟棤宓屽叆涓婁笅鏂囷級鏃惰皟鐢ㄣ€?
   */
  private async _fetchReplyContext(msgId: string): Promise<ReplyContext | null> {
    if (!msgId) return null;
    const numId = Number(msgId);
    if (!Number.isFinite(numId)) return null;
    try {
      const res = await this.callAction('get_msg', { message_id: numId }) as Record<string, unknown> | null;
      if (!res) return null;

      const senderRaw = res['sender'];
      const sender = (senderRaw && typeof senderRaw === 'object')
        ? (senderRaw as Record<string, unknown>) : {};
      const senderId = String(res['user_id'] ?? sender['user_id'] ?? '');
      const senderNickname =
        String(sender['card'] ?? '').trim() || String(sender['nickname'] ?? '').trim();

      let previewText = '';
      if (Array.isArray(res['message'])) {
        const parts: string[] = [];
        for (const seg of res['message'] as Array<Record<string, unknown>>) {
          const d = (seg['data'] && typeof seg['data'] === 'object')
            ? (seg['data'] as Record<string, unknown>) : {};
          if (seg['type'] === 'text') {
            const t = String(d['text'] ?? '').trim();
            if (t) parts.push(t);
          } else if (seg['type'] === 'image') {
            parts.push(Number(d['sub_type'] ?? -1) === 1 ? '[琛ㄦ儏鍖匽' : '[鍥剧墖]');
          } else if (seg['type'] === 'mface') {
            parts.push('[琛ㄦ儏鍖匽');
          } else if (seg['type'] === 'record') {
            parts.push('[璇煶]');
          }
        }
        previewText = parts.join(' ').trim().slice(0, 80);
      }
      if (!previewText && typeof res['raw_message'] === 'string') {
        previewText = res['raw_message'].trim().slice(0, 80);
      }

      return { senderId, senderNickname, previewText };
    } catch (err) {
      this.logger.warn('[napcat] 鑾峰彇寮曠敤娑堟伅鍐呭澶辫触', {
        msg_id: msgId,
        error: err instanceof Error ? err.message : String(err),
      });
      return null;
    }
  }
}

