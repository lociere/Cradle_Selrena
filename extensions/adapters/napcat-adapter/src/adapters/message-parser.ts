/**
 * OB11 Message Parser 鈥?message-parser.ts
 *
 * Parses raw OB11 message segments into a structured, typed ParsedMessage object.
 * This is the normalization step inside the adapter layer.
 * Output of this module is consumed by perception-builder to produce PerceptionEvent.
 */

import type { NapcatAdapterConfig } from '../../config/schema';
import type { OB11MessageEvent, OB11MessageSegment } from './ob11-types';

export interface MediaItem {
  modality: 'image' | 'video';
  uri: string;
  mime_type: string;
  semantic?: {
    text: string;
    source?: string;
    resolved?: boolean;
    confidence?: number;
  };
  metadata: Record<string, unknown>;
}

export interface ReplyContext {
  senderId: string;
  senderNickname: string;
  previewText: string;
}

export interface MessageTraits {
  isAtMessage: boolean;
  isReplyMessage: boolean;
  isReplyToSelf: boolean;
  hasFace: boolean;
  hasSticker: boolean;
  hasImage: boolean;
  hasVideo: boolean;
  hasRecord: boolean;
}

export interface ParsedMessage {
  sourceType: 'group' | 'private';
  sourceId: string;
  senderId: string;
  displayText: string;
  text: string;
  recordSource: string;
  mediaItems: MediaItem[];
  replyMessageId: string;
  replyContext: ReplyContext;
  hasMention: boolean;
  messageTraits: MessageTraits;
}

function guessMimeType(type: 'image' | 'video', uri: string): string {
  const lower = String(uri).toLowerCase();
  if (type === 'image') {
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.gif')) return 'image/gif';
    return 'image/jpeg';
  }
  if (lower.endsWith('.webm')) return 'video/webm';
  if (lower.endsWith('.mov')) return 'video/quicktime';
  return 'video/mp4';
}

/**
 * 鎻愬彇 OB11 鍥剧墖娈?summary 瀛楁涓殑璇箟鏍囩銆?
 * summary 鏍煎紡鍥哄畾涓?"[鏂囧瓧]"(濡?"[鏃╁畨]")锛屽幓鎺夋柟鎷彿鍙栫函鏂囧瓧銆?
 * 娉涘瀷鍗犱綅璇嶏紙鍥剧墖/鍔ㄥ浘绛夛級瑙嗕负鏃犺涔夛紝杩斿洖 null銆?
 */
const _GENERIC_SUMMARY_LABELS = new Set([
  '图片',
  '动图',
  '图',
  '动画',
  '表情',
  'gif',
  'GIF',
  'image',
  'photo',
]);

function decodeOb11Summary(raw: unknown): string {
  return String(raw ?? '')
    .replace(/&#91;/g, '[')
    .replace(/&#93;/g, ']')
    .replace(/&amp;/g, '&')
    .trim();
}

function extractSummaryLabel(data: Record<string, unknown>): string | null {
  const summary = decodeOb11Summary(data['summary']);
  const match = /^\[(.+)\]$/.exec(summary);
  if (!match) return null;
  const label = match[1].trim();
  if (!label || _GENERIC_SUMMARY_LABELS.has(label)) return null;
  return label;
}

function classifySpecialImage(data: Record<string, unknown>): 'sticker' | 'image' {
  // sub_type=1: 鑷畾涔夎〃鎯呭寘锛泂ub_type=7: QQ 杈撳叆鎺ㄨ崘琛ㄦ儏锛堣緭鍏ユ寮瑰嚭锛?
  const subType = Number(data['sub_type'] ?? data['subtype'] ?? -1);
  if (subType === 1 || subType === 7) return 'sticker';
  const hint = `${String(data['summary'] ?? '')} ${String(data['file'] ?? '')}`;
  if (/鍔ㄧ敾琛ㄦ儏|鏍囧噯琛ㄦ儏|琛ㄦ儏|sticker|mface|emoji/i.test(hint)) return 'sticker';
  return 'image';
}

function parseReplyContext(event: OB11MessageEvent, botSelfId: string, replyMessageId: string) {
  let parsedReplyMessageId = replyMessageId;
  let repliedSenderId = '';
  let repliedSenderNickname = '';
  let repliedPreviewText = '';

  if (event.reply && typeof event.reply === 'object') {
    const replyData = event.reply;
    const sender = replyData.sender ?? {};
    if (!parsedReplyMessageId) {
      parsedReplyMessageId = String(replyData.message_id ?? '');
    }
    repliedSenderId = String(replyData.user_id ?? sender.user_id ?? '');
    repliedSenderNickname = String(sender.card ?? sender.nickname ?? '').trim();

    if (Array.isArray(replyData.message)) {
      const previewParts: string[] = [];
      for (const seg of replyData.message as OB11MessageSegment[]) {
        if (!seg || typeof seg !== 'object') continue;
        if (seg.type === 'text') previewParts.push(String(seg.data['text'] ?? ''));
        else if (seg.type === 'at') previewParts.push(`@${String(seg.data['qq'] ?? '')}`);
      }
      repliedPreviewText = previewParts.join('').trim().slice(0, 80);
    } else if (typeof replyData.raw_message === 'string') {
      repliedPreviewText = replyData.raw_message.trim().slice(0, 80);
    }
  }

  const isReplyToSelf =
    !!repliedSenderId &&
    !!replyMessageId &&
    repliedSenderId === String(botSelfId);

  return { parsedReplyMessageId, repliedSenderId, repliedSenderNickname, repliedPreviewText, isReplyToSelf };
}

export function parseMessageSegments(
  event: OB11MessageEvent,
  botSelfId: string,
  config: NapcatAdapterConfig,
): ParsedMessage {
  const segments: OB11MessageSegment[] = Array.isArray(event.message) ? event.message : [];
  const textParts: string[] = [];
  const mediaItems: MediaItem[] = [];

  let hasMention = false;
  let hasReply = false;
  let hasFace = false;
  let hasSticker = false;
  let hasImage = false;
  let hasVideo = false;
  let hasRecord = false;
  let replyMessageId = '';
  let recordSource = '';

  const multimodalEnabled = config.ingress.multimodal?.enabled ?? false;

  for (const segment of segments) {
    if (!segment || typeof segment !== 'object') continue;
    const { type, data } = segment;

    if (type === 'text') {
      // 璺宠繃绾┖鐧芥锛堝父瑙佷簬 @mention 鍚庤嚜鍔ㄨ拷鍔犵殑 " " 鍒嗛殧绗︼級
      const textVal = String(data['text'] ?? '');
      if (textVal.trim()) textParts.push(textVal);
      continue;
    }
    if (type === 'at') {
      const qq = String(data['qq'] ?? '');
      textParts.push(`@${qq}`);
      if (qq && qq === String(botSelfId)) hasMention = true;
      continue;
    }
    if (type === 'reply') {
      hasReply = true;
      replyMessageId = String(data['id'] ?? '');
      continue;
    }
    if (type === 'face') {
      hasFace = true;
      textParts.push('[QQ琛ㄦ儏]');
      continue;
    }
    if (type === 'record') {
      recordSource = String(data['file'] ?? data['path'] ?? data['url'] ?? '');
      hasRecord = true;
      textParts.push('[璇煶娑堟伅]');
      continue;
    }
    if (type === 'image') {
      const uri = String(data['url'] ?? data['file'] ?? data['path'] ?? '');
      const imageKind = classifySpecialImage(data);
      const summaryLabel = extractSummaryLabel(data);
      if (imageKind === 'sticker') {
        hasSticker = true;
        // 濡傛灉鏈夎涔夋爣绛撅紙濡?鏃╁畨"锛夛紝鐩存帴鍛堢幇缁?AI锛涘惁鍒欎娇鐢ㄦ硾绉?
        textParts.push(summaryLabel ? `[${summaryLabel}]` : '[琛ㄦ儏鍖匽');
      } else {
        hasImage = true;
        textParts.push('[鍥剧墖]');
      }
      if (uri && multimodalEnabled) {
        mediaItems.push({
          modality: 'image',
          uri,
          mime_type: guessMimeType('image', uri),
          semantic:
            (imageKind === 'sticker' && summaryLabel)
              ? {
                  text: summaryLabel,
                  source: 'platform_summary',
                  resolved: true,
                  confidence: 0.95,
                }
              : undefined,
          metadata: {
            file_size: data['file_size'],
            visual_kind: imageKind,
          },
        });
      }
      continue;
    }
    if (type === 'video') {
      const uri = String(data['url'] ?? data['file'] ?? data['path'] ?? '');
      hasVideo = true;
      textParts.push('[瑙嗛]');
      if (uri && multimodalEnabled) {
        mediaItems.push({
          modality: 'video',
          uri,
          mime_type: guessMimeType('video', uri),
          semantic: undefined,
          metadata: { file_size: data['file_size'] },
        });
      }
      continue;
    }
    // QQ 鍟嗗煄澶ц〃鎯?/ 甯傚満琛ㄦ儏锛坢face锛?
    if (type === 'mface') {
      hasSticker = true;
      const mfaceLabel = extractSummaryLabel(data);
      textParts.push(mfaceLabel ? `[${mfaceLabel}]` : '[琛ㄦ儏鍖匽');
      const mfaceUrl = String(data['url'] ?? '');
      if (mfaceUrl && multimodalEnabled) {
        mediaItems.push({
          modality: 'image',
          uri: mfaceUrl,
          mime_type: 'image/gif',
          semantic: mfaceLabel
            ? {
                text: mfaceLabel,
                source: 'platform_summary',
                resolved: true,
                confidence: 0.95,
              }
            : undefined,
          metadata: {
            visual_kind: 'sticker',
          },
        });
      }
      continue;
    }
    // JSON / XML 鍗＄墖娑堟伅锛堝皬绋嬪簭銆佸垎浜摼鎺ョ瓑锛?
    if (type === 'json' || type === 'xml') {
      textParts.push('[鍗＄墖娑堟伅]');
      continue;
    }
    if (type === 'file') {
      textParts.push(`[鏂囦欢:${String(data['name'] ?? data['file'] ?? '鏈煡鏂囦欢')}]`);
    }
  }

  const replyCtx = parseReplyContext(event, botSelfId, replyMessageId);

  const sourceType = event.message_type === 'group' ? 'group' : 'private';
  const sourceId =
    sourceType === 'group' ? String(event.group_id ?? '') : String(event.user_id);
  const senderId = String(event.user_id);

  return {
    sourceType,
    sourceId,
    senderId,
    displayText: String(event.raw_message ?? textParts.join('')).trim(),
    text: textParts.join('').trim(),
    recordSource,
    mediaItems,
    replyMessageId: replyCtx.parsedReplyMessageId,
    replyContext: {
      senderId: replyCtx.repliedSenderId,
      senderNickname: replyCtx.repliedSenderNickname,
      previewText: replyCtx.repliedPreviewText,
    },
    hasMention,
    messageTraits: {
      isAtMessage: hasMention,
      isReplyMessage: hasReply,
      isReplyToSelf: replyCtx.isReplyToSelf,
      hasFace,
      hasSticker,
      hasImage,
      hasVideo,
      hasRecord,
    },
  };
}

