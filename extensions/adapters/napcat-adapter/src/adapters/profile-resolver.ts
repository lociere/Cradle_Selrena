/**
 * Sender Profile Resolver 鈥?profile-resolver.ts
 *
 * Resolves the display nickname for a message sender.
 * Uses a TTL cache to avoid redundant API calls.
 * Falls back to QQ ID when no name can be resolved.
 */

import type { IExtensionLogger } from '@cradle-selrena/protocol';
import type { OB11MessageEvent } from './ob11-types';
import type { ParsedMessage } from './message-parser';

type CallActionFn = (action: string, params: Record<string, unknown>) => Promise<unknown>;

interface CacheEntry {
  value: string;
  expiresAt: number;
}

export class SenderProfileResolver {
  private readonly _logger: IExtensionLogger;
  private readonly _callAction: CallActionFn;
  private readonly _cacheTtlMs: number;
  private readonly _cache = new Map<string, CacheEntry>();

  constructor(logger: IExtensionLogger, callAction: CallActionFn, cacheTtlMs: number) {
    this._logger = logger;
    this._callAction = callAction;
    this._cacheTtlMs = Number(cacheTtlMs) || 300_000;
  }

  async resolve(event: OB11MessageEvent, parsed: ParsedMessage): Promise<string> {
    const cacheKey = `${parsed.sourceType}:${parsed.sourceId}:${parsed.senderId}`;
    const now = Date.now();
    const cached = this._cache.get(cacheKey);
    if (cached && cached.expiresAt > now) return cached.value;

    const sender = event.sender ?? {};
    // card 鍙兘涓虹┖瀛楃涓诧紙缇ゅ憳鏈缃兢鏄电О锛夛紝姝ゆ椂搴斿洖閫€鍒?nickname
    // 浣跨敤 || 鑰岄潪 ?? 锛氱┖瀛楃涓茶涓烘棤鏁堝€?
    const card = String(sender.card ?? '').trim();
    const fallbackNick = String(sender.nickname ?? '').trim();
    let nickname = card || fallbackNick;

    if (!nickname) {
      nickname = await this._fetchNickname(parsed);
    }

    if (!nickname) {
      // 鍙?senderId 鏈?4 浣嶄綔涓哄尶鍚嶇煭鐮侊紝閬垮厤灏嗗钩鍙扮鏈?ID锛圦Q 鍙凤級鍐欏叆 AI Core 璁板繂
      const shortId = String(parsed.senderId || '').slice(-4) || '0000';
      nickname = `用户-${shortId}`;
    }

    this._cache.set(cacheKey, { value: nickname, expiresAt: now + this._cacheTtlMs });
    return nickname;
  }

  private async _fetchNickname(parsed: ParsedMessage): Promise<string> {
    try {
      if (parsed.sourceType === 'group') {
        const res = await this._callAction('get_group_member_info', {
          group_id: parsed.sourceId,
          user_id: parsed.senderId,
          no_cache: false,
        }) as Record<string, unknown> | null;
        // NapCat 杩斿洖 data 瀛楁涓惈 card/nickname锛宑ard 鍙兘涓虹┖瀛楃涓?
        const resCard = String(res?.['card'] ?? '').trim();
        const resNick = String(res?.['nickname'] ?? '').trim();
        return resCard || resNick;
      }

      const res = await this._callAction('get_stranger_info', {
        user_id: parsed.senderId,
        no_cache: false,
      }) as Record<string, unknown> | null;
      return String(res?.['nickname'] ?? '').trim();
    } catch (err) {
      this._logger.warn('获取发送者昵称失败，使用回退值', {
        source_type: parsed.sourceType,
        source_id: parsed.sourceId,
        sender_id: parsed.senderId,
        error: err instanceof Error ? err.message : String(err),
      });
      return '';
    }
  }
}

