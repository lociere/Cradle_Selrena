/**
 * Perception Builder — perception-builder.ts
 *
 * Cortex layer: converts parsed OB11 message data into a standardized
 * PerceptionRequest that the Soul layer can consume without any OB11 knowledge.
 *
 * This module is the final Vessel → Soul boundary gate.
 */

import type { NapcatPluginConfig } from '../../config/schema';
import type { OB11MessageEvent } from './ob11-types';
import type { ParsedMessage } from './message-parser';

// ─────────────────────────────────────────────────────────────────
// Inbound helpers
// ─────────────────────────────────────────────────────────────────

/**
 * Strip bot @-mentions and leading wake-words from incoming text
 * so Soul receives only the semantic content.
 */
export function cleanInboundText(
  text: string,
  event: OB11MessageEvent,
  config: NapcatPluginConfig,
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

/**
 * Determine whether a group message should enter the pipeline based on the
 * configured dispatch policy (all / mention_only / wake_word_only).
 */
export function shouldDispatchGroupMessage(
  parsed: ParsedMessage,
  originalText: string,
  config: NapcatPluginConfig,
): boolean {
  const policy = config.ingress.group_policy;
  const normalized = String(originalText).toLowerCase();
  const hasWakeWord = config.ingress.wake_words.some((w) => {
    const kw = String(w).trim().toLowerCase();
    return kw && normalized.includes(kw);
  });

  if (policy === 'all') return true;
  if (policy === 'mention_only') return parsed.messageTraits.isAtMessage;
  if (policy === 'wake_word_only') return hasWakeWord;
  return parsed.messageTraits.isAtMessage || hasWakeWord;
}

// ─────────────────────────────────────────────────────────────────
// PerceptionRequest builder
// ─────────────────────────────────────────────────────────────────

interface PerceptionInputItem {
  modality: string;
  text?: string;
  uri?: string;
  mime_type?: string;
  description_hint?: string;
  metadata: Record<string, unknown>;
}

interface PerceptionRequest {
  input: { items: PerceptionInputItem[] };
  scene_id: string;
  familiarity: number;
  source: {
    vessel_id: string;
    source_type: string;
    source_id: string;
  };
  routing: {
    session_policy: string;
    actor: { actor_id: string; actor_name: string };
  };
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

  const traits = labels.length > 0 ? labels.join('/') : '普通消息';
  const senderTag =
    parsed.sourceType === 'group'
      ? `[群成员:${nickname}(${parsed.senderId})]`
      : `[私聊用户:${nickname}(${parsed.senderId})]`;
  const replyTag = parsed.replyMessageId ? `[回复ID:${parsed.replyMessageId}]` : '';
  const replyTargetTag =
    parsed.replyContext.senderNickname || parsed.replyContext.senderId
      ? `[回复对象:${parsed.replyContext.senderNickname || parsed.replyContext.senderId}(${parsed.replyContext.senderId || 'unknown'})]`
      : '';
  const replyPreviewTag = parsed.replyContext.previewText
    ? `[回复内容预览:${parsed.replyContext.previewText}]`
    : '';

  return [senderTag, `[消息类型:${traits}]`, replyTag, replyTargetTag, replyPreviewTag, cleanText]
    .filter(Boolean)
    .join(' ')
    .trim();
}

/**
 * Build a standard PerceptionRequest from a parsed message.
 * Returns null if there is no actionable content (empty text, no media).
 */
export function buildPerceptionRequest(
  parsed: ParsedMessage,
  sceneId: string,
  nickname: string,
  cleanText: string,
  config: NapcatPluginConfig,
  isMainUser: boolean,
  sessionPolicy = 'by_source',
): PerceptionRequest | null {
  const inputItems: PerceptionInputItem[] = [];

  const textPayload = buildTextPayload(parsed, nickname, cleanText);
  if (textPayload) {
    inputItems.push({
      modality: 'text',
      text: textPayload,
      metadata: {
        sender_id: parsed.senderId,
        sender_nickname: nickname,
        message_traits: parsed.messageTraits,
        reply_context: parsed.replyContext,
        is_main_user: isMainUser,
      },
    });
  }

  for (const item of parsed.mediaItems) {
    inputItems.push({
      ...item,
      metadata: {
        ...item.metadata,
        sender_id: parsed.senderId,
        sender_nickname: nickname,
        message_traits: parsed.messageTraits,
        reply_context: parsed.replyContext,
        is_main_user: isMainUser,
      },
    });
  }

  if (inputItems.length === 0) return null;

  return {
    input: { items: inputItems },
    scene_id: sceneId,
    familiarity:
      parsed.sourceType === 'group'
        ? Number(config.ingress.familiarity.group ?? 0)
        : Number(config.ingress.familiarity.private ?? 0),
    source: {
      vessel_id: 'napcat-adapter',
      source_type: parsed.sourceType,
      source_id: parsed.sourceId,
    },
    routing: {
      session_policy: sessionPolicy,
      actor: { actor_id: parsed.senderId, actor_name: nickname },
    },
  };
}

// ─────────────────────────────────────────────────────────────────
// Outbound helpers
// ─────────────────────────────────────────────────────────────────

const EMOTION_WORDS =
  '开心|高兴|愉快|害羞|生气|愤怒|难过|委屈|傲娇|好奇|平静|冷静|happy|shy|angry|sulky|curious|sad|calm';
const PREFIX_PATTERNS = [
  new RegExp(
    `^[\\[\\(（【《<]\\s*(?:emotion|情绪)?\\s*[:：-]?\\s*(?:${EMOTION_WORDS})\\s*[\\]\\)）】》>]\\s*`,
    'i',
  ),
  new RegExp(`^(?:emotion|情绪)\\s*[:：-]\\s*(?:${EMOTION_WORDS})\\s*`, 'i'),
];

/**
 * Strip emotion-tag prefixes (e.g. "[emotion: happy]") from outbound reply text.
 */
export function cleanOutboundReply(text: string): string {
  let value = String(text).replace(/\r/g, '').trim();
  if (!value) return '';

  let changed = true;
  while (changed && value) {
    changed = false;
    for (const pattern of PREFIX_PATTERNS) {
      const next = value.replace(pattern, '').trim();
      if (next !== value) {
        value = next;
        changed = true;
      }
    }
  }

  return value;
}
