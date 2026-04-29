/**
 * IdentityRouter — 防腐网关身份路由器
 *
 * v4.5 Phase 1: Schema-First ACL (Anti-Corruption Layer)
 *
 * 职责：
 *   1. 将平台私有 ID (user_id/group_id) 映射为系统中立的 vessel_id
 *   2. 清洗 CQ 码等富文本协议，转化为中立 MultimodalContent
 *   3. 通过 Schema 校验组装标准 PerceptionMessageRequest 后才允许转发
 *
 * 设计原则：
 *   - 灵魂纯净：此网关之后的一切代码，不应看到任何平台私有字段
 *   - 位于 IngressGate 之前，是数据进入系统的第一道净化关卡
 */
import { randomUUID } from 'crypto';
import { getLogger } from '../logger/logger';
import type { PerceptionMessageRequest, PerceptionModalityItem } from '@cradle-selrena/protocol';

const logger = getLogger('identity-router');

// ── CQ 码解析正则 ─────────────────────────────────────────
const CQ_CODE_RE = /\[CQ:(\w+)(?:,([^\]]*))?\]/g;

/** vessel_id 映射条目 */
interface VesselMapping {
  vesselId: string;
  platform: string;
  createdAt: number;
}

/**
 * IdentityRouter 单例
 * 负责在消息进入系统前完成身份归一化与协议清洗
 */
export class IdentityRouter {
  private static _instance: IdentityRouter | null = null;

  /** platform:raw_id → vessel_id 映射缓存 */
  private _vesselMap: Map<string, VesselMapping> = new Map();

  public static get instance(): IdentityRouter {
    if (!IdentityRouter._instance) {
      IdentityRouter._instance = new IdentityRouter();
    }
    return IdentityRouter._instance;
  }

  private constructor() {}

  // ═══════════════════════════════════════════════════════════
  //  身份映射
  // ═══════════════════════════════════════════════════════════

  /**
   * 将平台私有 ID 映射为系统中立 vessel_id。
   * 若映射不存在则自动创建（首次接触等价于注册）。
   */
  public resolveVesselId(platform: string, rawId: string): string {
    const key = `${platform}:${rawId}`;
    const existing = this._vesselMap.get(key);
    if (existing) return existing.vesselId;

    const vesselId = `v_${randomUUID().replace(/-/g, '').slice(0, 12)}`;
    this._vesselMap.set(key, {
      vesselId,
      platform,
      createdAt: Date.now(),
    });
    logger.info('新 vessel 身份已注册', { platform, raw_id: rawId, vessel_id: vesselId });
    return vesselId;
  }

  /**
   * 批量导入已有映射（启动时从持久化层加载）
   */
  public loadMappings(entries: Array<{ platform: string; rawId: string; vesselId: string }>): void {
    for (const e of entries) {
      this._vesselMap.set(`${e.platform}:${e.rawId}`, {
        vesselId: e.vesselId,
        platform: e.platform,
        createdAt: Date.now(),
      });
    }
    logger.info('vessel 映射已加载', { count: entries.length });
  }

  // ═══════════════════════════════════════════════════════════
  //  协议清洗 — CQ 码 → 中立 MultimodalContent
  // ═══════════════════════════════════════════════════════════

  /**
   * 将含 CQ 码的原始文本清洗为纯文本 + 多模态条目列表。
   * CQ码语法: [CQ:type,key1=val1,key2=val2]
   */
  public sanitizeContent(rawText: string): { text: string; items: PerceptionModalityItem[] } {
    const items: PerceptionModalityItem[] = [];
    let lastIndex = 0;
    const textParts: string[] = [];

    let match: RegExpExecArray | null;
    CQ_CODE_RE.lastIndex = 0;
    while ((match = CQ_CODE_RE.exec(rawText)) !== null) {
      // 收集 CQ 码之前的纯文本
      if (match.index > lastIndex) {
        textParts.push(rawText.slice(lastIndex, match.index));
      }
      lastIndex = match.index + match[0].length;

      const cqType = match[1];
      const params = this._parseCQParams(match[2] || '');

      switch (cqType) {
        case 'image':
          items.push({
            modality: 'image',
            uri: params.url || params.file || '',
            mime_type: 'image/*',
            metadata: { original_cq: match[0] },
          });
          break;
        case 'record':
        case 'video':
          items.push({
            modality: 'video',
            uri: params.url || params.file || '',
            mime_type: cqType === 'record' ? 'audio/*' : 'video/*',
            metadata: { original_cq: match[0] },
          });
          break;
        case 'face':
          // QQ 表情 → 文本占位
          textParts.push(`[表情:${params.id || ''}]`);
          break;
        case 'at':
          // @某人 → 文本占位（不透传 qq= 字段）
          textParts.push(`@${params.name || '某人'}`);
          break;
        case 'reply':
          // 回复引用 → 忽略协议细节
          break;
        default:
          // 未知 CQ 码 → 静默丢弃，记录日志
          logger.debug('未知 CQ 码类型已丢弃', { cq_type: cqType });
          break;
      }
    }

    // 收集尾部纯文本
    if (lastIndex < rawText.length) {
      textParts.push(rawText.slice(lastIndex));
    }

    return {
      text: textParts.join('').trim(),
      items,
    };
  }

  // ═══════════════════════════════════════════════════════════
  //  组装标准感知请求
  // ═══════════════════════════════════════════════════════════

  /**
   * 从原始平台事件组装标准化 PerceptionMessageRequest。
   * 所有平台私有字段在此被剥离，之后的代码不再感知平台。
   */
  public assemblePerceptionRequest(rawEvent: {
    platform: string;
    rawUserId: string;
    rawGroupId?: string;
    rawText: string;
    sensoryType?: string;
    familiarity?: number;
    addressMode?: 'direct' | 'ambient';
    timestamp?: number;
  }): PerceptionMessageRequest {
    const vesselId = this.resolveVesselId(rawEvent.platform, rawEvent.rawUserId);
    const sourceType = rawEvent.rawGroupId ? 'group' : 'private';
    const sourceId = rawEvent.rawGroupId
      ? this.resolveVesselId(rawEvent.platform, rawEvent.rawGroupId)
      : vesselId;

    const { text, items } = this.sanitizeContent(rawEvent.rawText);
    const modality: string[] = ['text'];
    if (items.some(i => i.modality === 'image')) modality.push('image');
    if (items.some(i => i.modality === 'video')) modality.push('video');

    const traceId = randomUUID();

    const request: PerceptionMessageRequest = {
      id: traceId,
      sensoryType: rawEvent.sensoryType || 'chat',
      source: `${sourceType}:${sourceId}`,
      timestamp: rawEvent.timestamp || Date.now(),
      familiarity: rawEvent.familiarity ?? 0,
      address_mode: rawEvent.addressMode || 'direct',
      content: {
        text: text || undefined,
        modality,
        items: items.length > 0 ? items : undefined,
      },
    };

    logger.debug('感知请求已组装', {
      trace_id: traceId,
      vessel_id: vesselId,
      source: request.source,
      modality,
      item_count: items.length,
    });

    return request;
  }

  // ═══════════════════════════════════════════════════════════
  //  内部工具
  // ═══════════════════════════════════════════════════════════

  private _parseCQParams(raw: string): Record<string, string> {
    const params: Record<string, string> = {};
    if (!raw) return params;
    for (const pair of raw.split(',')) {
      const eqIdx = pair.indexOf('=');
      if (eqIdx > 0) {
        params[pair.slice(0, eqIdx).trim()] = pair.slice(eqIdx + 1).trim();
      }
    }
    return params;
  }
}
