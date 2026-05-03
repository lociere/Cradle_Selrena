/**
 * Perception Builder 鈥?perception-builder.ts
 *
 * Cortex layer: converts parsed OB11 message data into a standardized
 * PerceptionRequest that the AI core can consume without any OB11 knowledge.
 *
 * This module is the final adapter 鈫?AI Core boundary gate.
 */

import type { NapcatAdapterConfig } from '../../config/schema';
import type { OB11MessageEvent } from './ob11-types';
import type { ParsedMessage } from './message-parser';

// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
// Inbound helpers
// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

/**
 * Strip bot @-mentions and leading wake-words from incoming text
 * so the AI core receives only the semantic content.
 */
export function cleanInboundText(
  text: string,
  event: OB11MessageEvent,
  config: NapcatAdapterConfig,
  botSelfId: string,
): string {
  let value = String(text).replace(/\r/g, '').trim();
  if (!value) return value;

  if (event.message_type === 'group' && config.ingress.strip_self_mention) {
    const selfId = String(event.self_id ?? botSelfId ?? '');
    if (selfId) {
      value = value.replace(new RegExp(`@${selfId}\\s*`, 'g'), '').trim();
    }
  }

  if (config.ingress.strip_leading_wake_words) {
    for (const wakeWord of config.ingress.wake_words) {
      if (!wakeWord) continue;
      if (value.startsWith(wakeWord)) {
        value = value.slice(wakeWord.length).trim();
        break;
      }
    }
  }

  return value;
}

// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
// PerceptionRequest builder
// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

interface PerceptionInputItem {
  modality: string;
  text?: string;
  uri?: string;
  mime_type?: string;
  semantic?: {
    text: string;
    source?: string;
    resolved?: boolean;
    confidence?: number;
  };
  metadata: Record<string, unknown>;
}

/** Cortex 杈撳嚭锛氱粡娓呮礂鐨勬枃鏈拰濯掍綋椤瑰垪琛紝涓嶅惈浠讳綍閫傞厤鍣ㄧ鏈夎矾鐢卞瓧娈?*/
export interface CortexOutput {
  /** 涓绘枃鏈紙鏍煎紡鍖栧悗渚?AI Core 闃呰锛?*/
  formattedText: string;
  inputItems: PerceptionInputItem[];
}

function buildTextPayload(parsed: ParsedMessage, nickname: string, cleanText: string): string {
  const labels: string[] = [];
  if (parsed.messageTraits.isAtMessage) labels.push('@消息');
  if (parsed.messageTraits.isReplyMessage) labels.push('回复消息');
  if (parsed.messageTraits.isReplyToSelf) labels.push('回复月见');
  if (parsed.messageTraits.hasSticker) labels.push('表情包');
  if (parsed.messageTraits.hasFace) labels.push('QQ表情');
  if (parsed.messageTraits.hasImage) labels.push('图片');
  if (parsed.messageTraits.hasVideo) labels.push('视频');
  if (parsed.messageTraits.hasRecord) labels.push('语音消息');

  const traits = labels.length > 0 ? labels.join('/') : '普通消息';
  const senderTag =
    parsed.sourceType === 'group'
      ? `[群成员:${nickname}]`
      : `[私聊用户:${nickname}]`;
  // replyTargetTag 浠呬娇鐢ㄦ樀绉帮紙璇箟灞傦級锛屼笉浼犻€掍换浣曞钩鍙板唴閮?ID
  const replyTargetTag = parsed.replyContext.senderNickname
    ? `[回复对象:${parsed.replyContext.senderNickname}]`
    : '';
  const replyPreviewTag = parsed.replyContext.previewText
    ? `[回复内容预览:${parsed.replyContext.previewText}]`
    : '';

  return [senderTag, `[消息类型:${traits}]`, replyTargetTag, replyPreviewTag, cleanText]
    .filter(Boolean)
    .join(' ')
    .trim();
}

/**
 * Build a standard PerceptionRequest from a parsed message.
 * Returns null if there is no actionable content (empty text, no media).
 */
/**
 * Cortex 鏍稿績鍑芥暟锛氬皢瑙ｆ瀽鍚庣殑娑堟伅鏋勫缓涓?Adapter 鈫?AI Core 杈圭晫澶勭殑杈撳嚭銆?
 * 杩斿洖鏍煎紡鍖栨枃鏈拰濯掍綋椤瑰垪琛紱涓嶅惈浠讳綍閫傞厤鍣ㄧ鏈夎矾鐢卞瓧娈碉紙adapter_id銆乤ctor.id 绛夛級銆?
 * 杩斿洖 null 琛ㄧず娑堟伅鏃犲彲澶勭悊鍐呭锛堥潤榛樹涪寮冿級銆?
 */
export function buildPerceptionRequest(
  parsed: ParsedMessage,
  sceneId: string,
  nickname: string,
  cleanText: string,
  config: NapcatAdapterConfig,
  isMainUser: boolean,
  sessionPolicy = 'by_source',
): CortexOutput | null {
  const inputItems: PerceptionInputItem[] = [];

  const textPayload = buildTextPayload(parsed, nickname, cleanText);
  if (textPayload) {
    inputItems.push({
      modality: 'text',
      text: textPayload,
      metadata: {
        sender_nickname: nickname,
        is_main_user: isMainUser,
        // 浠ヤ笅涓鸿涔夋爣璁帮紝鍧囦负甯冨皵鍊硷紝鏃犱换浣曞钩鍙扮鏈夊瓧娈?
        is_at_message: parsed.messageTraits.isAtMessage,
        is_reply: parsed.messageTraits.isReplyMessage,
        is_reply_to_self: parsed.messageTraits.isReplyToSelf,
        has_sticker: parsed.messageTraits.hasSticker,
        has_image: parsed.messageTraits.hasImage,
        has_video: parsed.messageTraits.hasVideo,
        has_record: parsed.messageTraits.hasRecord,
        session_policy: sessionPolicy,
      },
    });
  }

  for (const item of parsed.mediaItems) {
    // 鍙紶閫掕涔夊瓧娈碉紝涓嶅睍寮€ item.metadata锛堥伩鍏?NapCat 骞冲彴瀛楁娓楅€忓叆 AI Core锛?
    inputItems.push({
      modality: item.modality,
      uri: item.uri,
      mime_type: item.mime_type,
      semantic: item.semantic,
      metadata: {
        visual_kind: item.metadata['visual_kind'] ?? item.modality,
        sender_nickname: nickname,
        is_main_user: isMainUser,
      },
    });
  }

  if (inputItems.length === 0) return null;

  const formattedText = inputItems.find((i) => i.modality === 'text')?.text ?? cleanText;
  return { formattedText, inputItems };
}

// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
// Outbound helpers
// 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

/**
 * 鏈堣浜鸿鍏ㄩ噺鎯呯华鏍囩锛堜笌 persona_injector.py 鍚屾缁存姢锛夈€?
 * 椤诲寘鍚?persona prompt 涓０鏄庣殑鎵€鏈夋爣绛捐瘝锛屼互鍙?LLM 鍙兘鑷杈撳嚭鐨勬墿灞曞悓涔夎瘝銆?
 */
const SELRENA_EMOTION_LABELS =
  // persona_injector.py 定义的核心情绪标签
  '平静|开心|疑惑|撒娇|严谨|害羞|生气|委屈|思考' +
  // 扩展同义词
  '|高兴|愉快|愤怒|难过|傲娇|好奇|冷静|激动|无奈|担心|兴奋' +
  // 鑻辨枃鍒悕
  '|calm|happy|curious|coy|tsundere|shy|angry|aggrieved|thinking' +
  '|joyful|pleased|furious|sad|peaceful|worried|excited|sulky';

/**
 * 鍏ㄥ眬鍖归厤鎯呯华鏍囩锛堜换鎰忎綅缃級锛歔寮€蹇僝 [emotion:happy] (emotion:shy) 銆婃€濊€冦€?绛夋牸寮忋€?
 * 浣跨敤鍏ㄥ眬 gi 鏍囧織锛屼竴娆℃浛鎹㈡秷闄ゆ墍鏈夊嚭鐜颁綅缃€?
 */
const GLOBAL_EMOTION_TAG_RE = new RegExp(
  `[\\[\\(（【]\\s*(?:emotion|情绪)?\\s*[:：]?\\s*(?:${SELRENA_EMOTION_LABELS})\\s*[\\]\\)）】]`,
  'gi',
);

/** 鏃犳嫭鍙峰墠缂€鏍煎紡锛氫粎鍖归厤琛岄鐨?"emotion: happy" 鎴?"鎯呯华锛氬紑蹇? 澹版槑銆?*/
const NAKED_EMOTION_PREFIX_RE = new RegExp(
  `^(?:emotion|情绪)\\s*[:：]\\s*(?:${SELRENA_EMOTION_LABELS})\\s*`,
  'i',
);

/**
 * 浠庡嚭绔欏洖澶嶆枃鏈腑娓呴櫎鍏ㄩ儴鎯呯华鏍囩銆?
 *
 * 澶勭悊鑼冨洿锛?
 *   - [寮€蹇僝 [emotion:happy] (shy) 绛夋墍鏈変綅缃紙鍓嶇紑銆佷腑闂淬€佹湯灏撅級
 *   - 鏃犳嫭鍙峰墠缂€锛歟motion: happy
 */
export function cleanOutboundReply(text: string): string {
  let value = String(text).replace(/\r/g, '').trim();
  if (!value) return '';

  // 鍏ㄥ眬鍘婚櫎鎵€鏈夋嫭鍙峰舰寮忔儏缁爣绛撅紙涓嶉檺浣嶇疆锛?
  value = value.replace(GLOBAL_EMOTION_TAG_RE, '').trim();
  // 鍘婚櫎鏃犳嫭鍙峰墠缂€褰㈠紡
  value = value.replace(NAKED_EMOTION_PREFIX_RE, '').trim();
  // 娓呯悊澶氫綑杩炵画绌虹櫧
  value = value.replace(/\s{2,}/g, ' ').trim();

  return value;
}

