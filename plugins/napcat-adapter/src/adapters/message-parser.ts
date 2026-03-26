/**
 * OB11 Message Parser — message-parser.ts
 *
 * Parses raw OB11 message segments into a structured, typed ParsedMessage object.
 * This is the Cortex pre-processing step inside the Vessel layer.
 * Output of this module is consumed by perception-builder to produce PerceptionEvent.
 */

import type { NapcatPluginConfig } from '../../config/schema';
import type { OB11MessageEvent, OB11MessageSegment } from './ob11-types';

export interface MediaItem {
  modality: 'image' | 'video';
  uri: string;
  mime_type: string;
  description_hint: string;
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

function classifySpecialImage(data: Record<string, unknown>): 'sticker' | 'image' {
  const hint = `${String(data['summary'] ?? '')} ${String(data['file'] ?? '')}`;
  if (/标准表情|表情|sticker|mface|emoji/i.test(hint)) return 'sticker';
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
  config: NapcatPluginConfig,
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
  let replyMessageId = '';
  let recordSource = '';

  const multimodalEnabled = config.ingress.multimodal?.enabled ?? false;

  for (const segment of segments) {
    if (!segment || typeof segment !== 'object') continue;
    const { type, data } = segment;

    if (type === 'text') {
      textParts.push(String(data['text'] ?? ''));
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
      textParts.push('[QQ表情]');
      continue;
    }
    if (type === 'record') {
      recordSource = String(data['file'] ?? data['path'] ?? data['url'] ?? '');
      continue;
    }
    if (type === 'image') {
      const uri = String(data['url'] ?? data['file'] ?? data['path'] ?? '');
      const imageKind = classifySpecialImage(data);
      if (imageKind === 'sticker') {
        hasSticker = true;
        textParts.push('[表情包]');
      } else {
        hasImage = true;
        textParts.push('[图片]');
      }
      if (uri && multimodalEnabled) {
        mediaItems.push({
          modality: 'image',
          uri,
          mime_type: guessMimeType('image', uri),
          description_hint: String(data['summary'] ?? ''),
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
      textParts.push('[视频]');
      if (uri && multimodalEnabled) {
        mediaItems.push({
          modality: 'video',
          uri,
          mime_type: guessMimeType('video', uri),
          description_hint: String(data['summary'] ?? ''),
          metadata: { file_size: data['file_size'] },
        });
      }
      continue;
    }
    if (type === 'file') {
      textParts.push(`[文件:${String(data['name'] ?? data['file'] ?? '未知文件')}]`);
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
    },
  };
}
