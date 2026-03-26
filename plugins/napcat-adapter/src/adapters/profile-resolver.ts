/**
 * Sender Profile Resolver — profile-resolver.ts
 *
 * Resolves the display nickname for a message sender.
 * Uses a TTL cache to avoid redundant API calls.
 * Falls back to QQ ID when no name can be resolved.
 */

import type { IPluginLogger } from '@cradle-selrena/protocol';
import type { OB11MessageEvent } from './ob11-types';
import type { ParsedMessage } from './message-parser';

type CallActionFn = (action: string, params: Record<string, unknown>) => Promise<unknown>;

interface CacheEntry {
  value: string;
  expiresAt: number;
}

export class SenderProfileResolver {
  private readonly _logger: IPluginLogger;
  private readonly _callAction: CallActionFn;
  private readonly _cacheTtlMs: number;
  private readonly _cache = new Map<string, CacheEntry>();

  constructor(logger: IPluginLogger, callAction: CallActionFn, cacheTtlMs: number) {
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
    let nickname = String(sender.card ?? sender.nickname ?? '').trim();

    if (!nickname) {
      nickname = await this._fetchNickname(parsed);
    }

    if (!nickname) {
      nickname = `QQ-${parsed.senderId || 'unknown'}`;
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
        return String(
          (res && (res['card'] ?? res['nickname'] ?? (res['data'] as Record<string, unknown> | undefined)?.['card'] ?? (res['data'] as Record<string, unknown> | undefined)?.['nickname'])) ?? '',
        ).trim();
      }

      const res = await this._callAction('get_stranger_info', {
        user_id: parsed.senderId,
        no_cache: false,
      }) as Record<string, unknown> | null;
      return String(
        (res && (res['nickname'] ?? (res['data'] as Record<string, unknown> | undefined)?.['nickname'])) ?? '',
      ).trim();
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
