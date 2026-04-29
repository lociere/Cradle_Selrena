/**
 * InboundPipeline — 入站消息处理管道
 *
 * 职责：
 *   - 接收已归一化的 OB11MessageEvent，执行 Cortex 层处理
 *   - 基础过滤（ignore_self / blocked / enabled）
 *   - 解析消息段 → 构建 PerceptionEvent → 注入 Soul
 *   - 写入插件短期记忆（含被过滤的背景消息）
 *
 * 层级说明：
 *   此模块属于 Vessel 层 Cortex，负责将 OB11 协议数据清洗为标准格式。
 *   向 Soul 传递的 PerceptionEvent.content 仅含语义数据，不含任何平台私有字段。
 *   入站防护（速率限制/熔断）由内核 PerceptionAppService 透明处理，插件无需感知。
 */

import crypto from 'crypto';

import type {
  PerceptionEvent,
  PerceptionModalityItem,
  IPluginLogger,
  IPerceptionPort,
  ISceneAttentionPort,
} from '@cradle-selrena/protocol';
import type { NapcatPluginConfig } from '../../config/schema';
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
    private readonly config: NapcatPluginConfig,
    private readonly logger: IPluginLogger,
    private readonly perception: IPerceptionPort,
    private readonly sceneAttention: ISceneAttentionPort,
    /** 由主插件持有并在断连时清空，此处共享引用 */
    private readonly activeChannels: Set<string>,
    private readonly router: ReplyRouter,
    private readonly profileResolver: SenderProfileResolver,
    private readonly memoryManager: ContextMemoryManager,
    /** NapCat action 调用（用于 get_msg、get_group_member_info 等） */
    private readonly callAction: (action: string, params: Record<string, unknown>) => Promise<unknown>,
  ) {}

  /**
   * 处理单条 OB11 事件。
   * 非 message 类型的帧（心跳、lifecycle 等）直接静默丢弃。
   */
  async process(event: OB11MessageEvent): Promise<void> {
    if ((event as Record<string, unknown>)['post_type'] !== 'message') return;

    this.logger.debug('[napcat] 收到消息事件', {
      message_type: event.message_type,
      user_id: event.user_id,
      group_id: event.group_id,
    });

    // self_id = 机器人自己的 QQ 号（来自 OB11 事件本身），用于过滤自发消息
    const botSelfId = String(event.self_id ?? '');
    // main_user.qq = 机器人主人的 QQ 号，用于 isMainUser 标记（与过滤无关）
    const mainUserQq = String(this.config.main_user.qq ?? '');

    // ── 基础过滤 ────────────────────────────────────────────────
    if (this.config.ingress.ignore_self && String(event.user_id) === botSelfId) return;
    if (this.config.ingress.blocked_user_ids.includes(String(event.user_id))) return;
    if (
      event.message_type === 'group' &&
      this.config.ingress.blocked_group_ids.includes(String(event.group_id ?? ''))
    )
      return;
    if (event.message_type === 'private' && !this.config.ingress.private_enabled) return;
    if (event.message_type === 'group' && !this.config.ingress.group_enabled) return;

    // ── Cortex：解析 OB11 消息段 ─────────────────────────────────
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

    // reply 段仅携带消息 ID，通过 get_msg 异步补全 sender 和内容摘要
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

    this.logger.info('[napcat] 收到消息', {
      scene: parsed.sourceType === 'group'
        ? `群${parsed.sourceId}${event['group_name'] ? `(${String(event['group_name'])})` : ''}`
        : `私聊:${parsed.senderId}`,
      nickname,
      text: parsed.text.slice(0, 80) || '(空)',
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

    // ── 注意力策略门控（纯同步，最先执行，避免非焦点期消息触发昂贵的异步调用）──
    // sourceFocusPolicy 由 napcat 插件在激活时通过 registerSourcePolicies 注入内核，
    // 此处从适配器配置中读取对应来源类型的策略，与内核状态保持一致。
    const sourceFocusPolicy =
      ((this.config.ingress.source_focus_policies ?? {}) as Record<string, string>)[
        parsed.sourceType
      ] ?? 'always_focused';

    // 唤醒词检测：仅看消息内容本身（@机器人 或 包含 wake_words 关键词）。
    // isMainUser 不参与此处判断——主用户的特殊响应优先级由 source_focus_policies 配置
    // 控制（如私聊配置为 always_focused），不在代码中硬编码，保持策略与逻辑分离。
    // 使用 parsed.text 而非 cleanText，因为 strip_leading_wake_words 可能已将
    // 开头的唤醒词剥离，会导致检测失败。
    const containsWakeWord =
      parsed.messageTraits.isAtMessage ||
      this.config.ingress.wake_words.some((w: string) => w && parsed.text.includes(w));

    // 读取内核当前维护的频道焦点状态（由 LifeClockManager 的 per-channel 计时器管理）
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
      // 非焦点期消息：写入背景记忆供下次群聊上下文使用，不触发 AI 层
      await this.memoryManager.appendInbound(memParams);
      return;
    }

    // ── 通过门控后：执行耗时操作并构建感知事件 ────────────────────
    // 任何通过焦点门控的消息都续期不活跃超时窗口。
    // 这确保超时从"最后一次活动"（而非唤醒词触发时刻）开始计算，
    // 避免用户在等待 AI 回复时焦点窗口悄然耗尽。
    // 在 inject 之前通知内核，确保 Soul 极速响应时焦点状态已就绪。
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

    // 群聊背景上下文：仅在注入时才异步拉取，避免非焦点消息触发无用 IO
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

    // address_mode：Vessel Cortex 将平台信号归一化为语义寻址模式，屏蔽平台细节。
    // always_focused（私聊）或含唤醒词 → direct（月见被明确呼唤，预期回复）
    // 焦点窗口内的普通群聊消息 → ambient（月见可自主决定是否开口）
    const addressMode: 'direct' | 'ambient' =
      sourceFocusPolicy === 'always_focused' || containsWakeWord
        ? 'direct'
        : 'ambient';

    // PerceptionEvent.content 严格只携带语义数据，无任何 Vessel 私有字段
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

    // 登记回复路由（必须在 inject 之前，避免 Soul 极速回复时找不到路由）
    this.router.register(eventId, {
      target_type: parsed.sourceType,
      target_id: parsed.sourceType === 'group' ? parsed.sourceId : parsed.senderId,
      sender_id: parsed.senderId,
    });

    this.activeChannels.add(sceneId);
    this.perception.inject(perceptionEvent);

    // 写入插件短期记忆（按 scene_id 自动隔离：私聊每用户、群聊每群）
    await this.memoryManager.appendInbound(memParams);
  }

  /**
   * 通过 NapCat get_msg API 补全被引用消息的发送者和内容摘要。
   * 仅在 reply 段只有 ID（无嵌入上下文）时调用。
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
            parts.push(Number(d['sub_type'] ?? -1) === 1 ? '[表情包]' : '[图片]');
          } else if (seg['type'] === 'mface') {
            parts.push('[表情包]');
          } else if (seg['type'] === 'record') {
            parts.push('[语音]');
          }
        }
        previewText = parts.join(' ').trim().slice(0, 80);
      }
      if (!previewText && typeof res['raw_message'] === 'string') {
        previewText = res['raw_message'].trim().slice(0, 80);
      }

      return { senderId, senderNickname, previewText };
    } catch (err) {
      this.logger.warn('[napcat] 获取引用消息内容失败', {
        msg_id: msgId,
        error: err instanceof Error ? err.message : String(err),
      });
      return null;
    }
  }
}
