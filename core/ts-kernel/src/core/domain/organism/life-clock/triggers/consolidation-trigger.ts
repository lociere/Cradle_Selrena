/**
 * ConsolidationTrigger — 记忆固化触发器
 *
 * v4.5 Phase 4: Async Memory Consolidation Engine
 *
 * 职责：
 *   当检测到某个场景会话处于空闲状态（超过阈值时间未交互），
 *   或工作记忆 Token 即将触碰 Zone B 水位线时，
 *   向 Python AI 层触发 ConsolidateMemoryEvent，启动短转长记忆固化。
 *
 * 设计原则：
 *   - 实现 AttentionTrigger 接口，由 LifeClockManager 注册
 *   - 不直接调用 Python，仅发布事件/通知 LifeClockManager 回调
 *   - 空闲检测基于最后交互时间戳
 */
import { getLogger } from '../../../../foundation/logger/logger';

const logger = getLogger('consolidation-trigger');

/** 记忆固化触发结果 */
export interface ConsolidationTriggerResult {
  shouldConsolidate: boolean;
  sceneId: string;
  reason: 'idle_timeout' | 'zone_b_pressure';
}

/** 场景活跃状态追踪 */
interface SceneActivity {
  lastInteractionAt: number;
  messageCount: number;
}

/**
 * 记忆固化触发器
 *
 * 被 LifeClockManager 在心跳循环中调用 evaluate()，
 * 检测所有活跃场景是否需要触发短转长记忆固化。
 */
export class ConsolidationTrigger {
  /** 空闲超时阈值（毫秒），默认 2 小时 */
  private _idleTimeoutMs: number = 2 * 60 * 60 * 1000;
  /** 最小消息数 — 消息太少不值得固化 */
  private _minMessagesForConsolidation: number = 5;
  /** 已触发固化的场景冷却（避免重复触发） */
  private _consolidationCooldown: Map<string, number> = new Map();
  /** 冷却时间（毫秒），固化后 30 分钟内不再触发 */
  private _cooldownMs: number = 30 * 60 * 1000;

  /** 场景活跃状态 */
  private _sceneActivities: Map<string, SceneActivity> = new Map();

  constructor(options?: {
    idleTimeoutMs?: number;
    minMessages?: number;
    cooldownMs?: number;
  }) {
    if (options?.idleTimeoutMs) this._idleTimeoutMs = options.idleTimeoutMs;
    if (options?.minMessages) this._minMessagesForConsolidation = options.minMessages;
    if (options?.cooldownMs) this._cooldownMs = options.cooldownMs;
  }

  /**
   * 记录场景交互活动（由外部在消息处理时调用）
   */
  public recordActivity(sceneId: string): void {
    const existing = this._sceneActivities.get(sceneId);
    if (existing) {
      existing.lastInteractionAt = Date.now();
      existing.messageCount++;
    } else {
      this._sceneActivities.set(sceneId, {
        lastInteractionAt: Date.now(),
        messageCount: 1,
      });
    }
  }

  /**
   * 评估所有活跃场景，返回需要固化的场景列表。
   * 由 LifeClockManager 在心跳循环中调用。
   */
  public evaluate(): ConsolidationTriggerResult[] {
    const now = Date.now();
    const results: ConsolidationTriggerResult[] = [];

    for (const [sceneId, activity] of this._sceneActivities) {
      // 检查冷却期
      const lastConsolidation = this._consolidationCooldown.get(sceneId) ?? 0;
      if (now - lastConsolidation < this._cooldownMs) continue;

      // 消息数不足，跳过
      if (activity.messageCount < this._minMessagesForConsolidation) continue;

      // 空闲超时检测
      const idleDuration = now - activity.lastInteractionAt;
      if (idleDuration >= this._idleTimeoutMs) {
        results.push({
          shouldConsolidate: true,
          sceneId,
          reason: 'idle_timeout',
        });
        logger.info('空闲超时触发记忆固化', {
          scene_id: sceneId,
          idle_ms: idleDuration,
          message_count: activity.messageCount,
        });
      }
    }

    return results;
  }

  /**
   * 标记场景已完成固化（进入冷却期并重置计数）
   */
  public markConsolidated(sceneId: string): void {
    this._consolidationCooldown.set(sceneId, Date.now());
    const activity = this._sceneActivities.get(sceneId);
    if (activity) {
      activity.messageCount = 0;
    }
  }

  /**
   * 清理不再活跃的场景（释放内存）
   */
  public pruneInactive(maxInactiveMs: number = 24 * 60 * 60 * 1000): void {
    const now = Date.now();
    for (const [sceneId, activity] of this._sceneActivities) {
      if (now - activity.lastInteractionAt > maxInactiveMs) {
        this._sceneActivities.delete(sceneId);
        this._consolidationCooldown.delete(sceneId);
      }
    }
  }
}
