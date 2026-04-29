/**
 * 生命时钟管理器
 * 驱动月见的主动思维，实现「活着」的核心特性
 * 按配置的间隔发送心跳给Python AI层，触发主动思维生成
 */
import { ConfigManager } from "../../../foundation/config/config-manager";
import { getLogger } from "../../../foundation/logger/logger";
import { EventBus } from "../../../foundation/event-bus/event-bus";
import {
  IAICapabilityPort,
  SceneAttentionChangedEvent,
  OrganismAttentionChangedEvent,
  OrganismAttentionMode,
  SourceAttentionPolicy,
  createTraceContext,
} from "@cradle-selrena/protocol";
import { AttentionTrigger, AttentionTriggerResult } from "./triggers/attention-trigger";
import { WakeKeywordTrigger } from "./triggers/wake-keyword-trigger";
import { ConsolidationTrigger, ConsolidationTriggerResult } from "./triggers/consolidation-trigger";

const logger = getLogger("life-clock-manager");

export type AttentionMode = "standby" | "ambient" | "focused";

/**
 * 生命时钟管理器
 * 单例模式
 */
export class LifeClockManager {
  private static _instance: LifeClockManager | null = null;
  private _timer: NodeJS.Timeout | null = null;
  private _isRunning: boolean = false;
  private _mode: AttentionMode = "standby";
  private _focusedIntervalMs: number = 10000;
  private _ambientIntervalMs: number = 45000;
  private _defaultMode: AttentionMode = "standby";
  private _focusDurationMs: number = 180000;
  private _focusOnAnyChat: boolean = false;
  private _summonKeywords: string[] = [];
  private _activeThoughtModes: Set<AttentionMode> = new Set(["ambient", "focused"]);
  private _heartbeatEnabled: boolean = true;
  /** 由插件通过 registerSourcePolicies 注入，不从全局配置读取 */
  private _sourceFocusPolicies: Record<string, SourceAttentionPolicy> = {};
  private readonly _channelFocusStates: Map<string, boolean> = new Map();
  /** per-channel 焦点超时计时器，与 _focusDurationMs 联动 */
  private readonly _channelFocusTimers: Map<string, NodeJS.Timeout> = new Map();
  private readonly _triggers: Map<string, AttentionTrigger> = new Map();
  /** v4.5: 记忆固化触发器 */
  private _consolidationTrigger: ConsolidationTrigger | null = null;
  private _sceneAttentionHandler: ((event: SceneAttentionChangedEvent) => Promise<void>) | null = null;
  private _aiProxy!: IAICapabilityPort;

  /**
   * 获取单例实例
   */
  public static get instance(): LifeClockManager {
    if (!LifeClockManager._instance) {
      LifeClockManager._instance = new LifeClockManager();
    }
    return LifeClockManager._instance;
  }

  private constructor() {}

  /**
   * 初始化生命时钟管理器
   */
  public async init(aiProxy: IAICapabilityPort): Promise<void> {
    this._aiProxy = aiProxy;
    const config = ConfigManager.instance.getConfig();
    const lifeClock = config.persona.inference.life_clock;
    this._focusedIntervalMs = lifeClock.focused_interval_ms;
    this._ambientIntervalMs = lifeClock.ambient_interval_ms;
    this._defaultMode = lifeClock.default_mode;
    this._mode = this._defaultMode;
    this._focusDurationMs = lifeClock.focus_duration_ms;
    this._focusOnAnyChat = lifeClock.focus_on_any_chat;
    this._summonKeywords = lifeClock.summon_keywords;
    this._activeThoughtModes = new Set(lifeClock.active_thought_modes);
    this._heartbeatEnabled = this._activeThoughtModes.size > 0;
    this.ensureDefaultTriggers();

    // 订阅频道场景注意力变更事件，更新有机体状态
    // ⚠️ 安全约束：handler 内部禁止使用 await。
    //    EventBus.publish 通过 Promise.all 并发调用所有 handler，若此处挂起，
    //    其他事件 handler 会插入执行，导致 _channelFocusStates/_channelFocusTimers 中间状态被读到。
    //    Node.js 单线程模型仅在同步执行期间保证原子性。
    this._sceneAttentionHandler = async (event) => {
      const e = event as SceneAttentionChangedEvent;
      this._channelFocusStates.set(e.channelId, e.focused);

      // per-channel 焦点超时：focus=true 时重置/启动倒计时，focus=false 时清除
      const existing = this._channelFocusTimers.get(e.channelId);
      if (existing) {
        clearTimeout(existing);
        this._channelFocusTimers.delete(e.channelId);
      }
      if (e.focused) {
        const effectiveDuration = e.durationMs ?? this._focusDurationMs;
        const channelId = e.channelId;
        const timer = setTimeout(() => {
          this._channelFocusStates.set(channelId, false);
          this._channelFocusTimers.delete(channelId);
          // 若无其他频道仍处于焦点状态，同步将有机体模式回退为默认值
          const stillFocused = Array.from(this._channelFocusStates.values()).some(v => v);
          if (!stillFocused) {
            this._setModeBySceneAttention(this._defaultMode, 'scene_attention_timeout');
          }
          this._updateOrganismAttention();
          logger.debug('频道焦点超时，自动重置', { channelId, duration_ms: effectiveDuration });
        }, effectiveDuration);
        this._channelFocusTimers.set(e.channelId, timer);

        // 频道进入焦点 → 有机体同步切换到 focused 模式（加速心跳与防抖响应）
        // 不依赖 scheduleFocusReset：超时由上方 per-channel timer 统一管理
        this._setModeBySceneAttention('focused', `scene_attention_${e.channelId}`);
      } else {
        // 显式取消焦点（如机器人离开群组），若无其他频道仍聚焦则退出 focused 模式
        const anyFocused = Array.from(this._channelFocusStates.values()).some(v => v);
        if (!anyFocused) {
          this._setModeBySceneAttention(this._defaultMode, 'scene_attention_unfocused');
        }
      }

      this._updateOrganismAttention();
    };
    EventBus.instance.subscribe('SceneAttentionChangedEvent', this._sceneAttentionHandler);

    logger.info("生命时钟管理器初始化完成", {
      focused_interval_ms: this._focusedIntervalMs,
      ambient_interval_ms: this._ambientIntervalMs,
      default_mode: this._defaultMode,
      focus_duration_ms: this._focusDurationMs,
      focus_on_any_chat: this._focusOnAnyChat,
      summon_keywords: this._summonKeywords,
      active_thought_modes: Array.from(this._activeThoughtModes),
      heartbeat_enabled: this._heartbeatEnabled,
    });
  }

  /**
   * 启动生命时钟
   */
  public start(): void {
    if (this._isRunning) {
      logger.warn("生命时钟已在运行中，跳过重复启动");
      return;
    }

    logger.info("生命时钟启动");
    this._isRunning = true;
    this._mode = this._defaultMode;

    if (!this._heartbeatEnabled) {
      logger.info("主动思维未启用，生命时钟不启动心跳循环");
      return;
    }

    this.startHeartbeatLoop();
  }

  /**
   * 启动心跳循环
   * 仅在当前模式属于 activeThoughtModes 时才调度下一次心跳；
   * 若模式切换为 standby，循环自然终止，不打印跳过日志。
   */
  private startHeartbeatLoop(): void {
    if (!this._isRunning) return;

    // 当前模式不需要主动思维时不调度心跳，避免无用定时器和噪音日志
    if (!this._activeThoughtModes.has(this._mode)) return;

    const interval = this._mode === "focused" ? this._focusedIntervalMs : this._ambientIntervalMs;

    this._timer = setTimeout(async () => {  
      if (!this._isRunning) return;

      try {
        // 检查Python AI层是否就绪
        if (!this._aiProxy.isReady) {
          logger.warn("Python AI层未就绪，跳过本次心跳");
          // AI未就绪时仍继续循环（稍后重试），但不触发主动思维
          this.startHeartbeatLoop();
          return;
        }

        // 发送生命心跳，触发主动思维
        await this._aiProxy.sendLifeHeartbeat({ attention_mode: this._mode });

        // v4.5: 评估记忆固化触发器
        if (this._consolidationTrigger) {
          const consolidationResults = this._consolidationTrigger.evaluate();
          for (const result of consolidationResults) {
            if (result.shouldConsolidate) {
              try {
                await this._aiProxy.consolidateMemory({
                  scene_id: result.sceneId,
                  reason: result.reason,
                });
                this._consolidationTrigger.markConsolidated(result.sceneId);
                logger.info('记忆固化完成', { scene_id: result.sceneId, reason: result.reason });
              } catch (consolidateError) {
                logger.error('记忆固化失败', {
                  scene_id: result.sceneId,
                  error: (consolidateError as Error).message,
                });
              }
            }
          }
        }
      } catch (error) {
        logger.error("生命心跳执行异常", { error: (error as Error).message });
      } finally {
        // 继续下一次循环（若模式已离开 activeThoughtModes，循环自然停止）
        this.startHeartbeatLoop();
      }
    }, interval);
  }

  /**
   * 消息触发注意力状态变化：支持“呼唤后聚焦”与“任意聊天聚焦”两种策略
   */
  public onUserMessage(content: string, sourceType: string = "unknown"): void {
    // 无论心跳是否启用，焦点状态变更都要生效（影响防抖时间窗口）
    if (!this._isRunning) return;
    const normalized = String(content || "");
    const normalizedSource = String(sourceType || "unknown").toLowerCase();
    const policy = this.resolveSourcePolicy(normalizedSource);
    const trigger = this.evaluateTriggers(normalized, normalizedSource);

    // v4.5: 记录场景活动，供固化触发器判断空闲超时
    if (this._consolidationTrigger) {
      this._consolidationTrigger.recordActivity(normalizedSource);
    }

    if (policy === "ignore") {
      return;
    }

    if (policy === "always_focused") {
      return;
    }

    if (policy === "wake_word_focus" || policy === "wake_word_focus_with_timeout") {
      return;
    }
  }

  /**
   * 手动切換注意力模式（焦点超时完全由 per-channel 计时器管理，此处不再维护全局重置计时器）
   */
  public setMode(mode: AttentionMode, reason: string = "manual"): void {
    if (this._mode === mode) return;

    const prev = this._mode;
    this._mode = mode;
    logger.info("注意力模式切换", { from: prev, to: mode, reason });
    this.restartLoop();
  }

  /**
   * 重启心跳循环
   */
  private restartLoop(): void {
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
    if (this._isRunning) {
      this.startHeartbeatLoop();
    }
  }

  /**
   * 由 SceneAttentionChangedEvent 驱动的模式切换。
   * 焦点超时完全由 _sceneAttentionHandler 内的 per-channel 计时器统一管理。
   */
  private _setModeBySceneAttention(mode: AttentionMode, reason: string): void {
    if (this._mode === mode) return;
    const prev = this._mode;
    this._mode = mode;
    logger.info('注意力模式切换', { from: prev, to: mode, reason });
    this.restartLoop();
  }

  /**
   * 获取当前时钟状态
   */
  public get state(): { isRunning: boolean; mode: AttentionMode } {
    return {
      isRunning: this._isRunning,
      mode: this._mode,
    };
  }

  /**
   * 根据各频道聚焦状态计算并发布有机体注意力变化事件
   */
  private _updateOrganismAttention(): void {
    const focusedChannels = Array.from(this._channelFocusStates.entries())
      .filter(([, focused]) => focused)
      .map(([channelId]) => channelId);

    const mode: OrganismAttentionMode =
      focusedChannels.length > 0
        ? 'ACTIVE'
        : this._mode === 'ambient'
        ? 'PASSIVE'
        : 'IDLE';

    EventBus.instance.publish(
      new OrganismAttentionChangedEvent(
        { mode, focusedChannels },
        createTraceContext()
      )
    );
  }

  /**
   * 停止生命时钟，优雅停机
   */
  public stop(): void {
    if (!this._isRunning) return;
    logger.info("生命时钟停止");
    this._isRunning = false;
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
    // 取消订阅事件，避免内存泄漏
    if (this._sceneAttentionHandler) {
      EventBus.instance.unsubscribe('SceneAttentionChangedEvent', this._sceneAttentionHandler);
      this._sceneAttentionHandler = null;
    }
    // 清理所有 per-channel 焦点计时器
    for (const timer of this._channelFocusTimers.values()) {
      clearTimeout(timer);
    }
    this._channelFocusTimers.clear();
    this._channelFocusStates.clear();
    // v4.5: 清理不活跃场景缓存
    if (this._consolidationTrigger) {
      this._consolidationTrigger.pruneInactive();
    }
  }

  private resolveSourcePolicy(sourceType: string): SourceAttentionPolicy {
    return this._sourceFocusPolicies[sourceType]
      ?? this._sourceFocusPolicies["unknown"]
      ?? "chat_or_wake_focus_with_timeout";
  }

  /**
   * 注册来源类型的注意力策略（由插件在激活时注入）。
   * 重复注册同一 sourceType 时后注册覆盖先注册。
   */
  public registerSourcePolicies(policies: Record<string, SourceAttentionPolicy>): void {
    for (const [sourceType, policy] of Object.entries(policies)) {
      this._sourceFocusPolicies[sourceType] = policy;
    }
    logger.info("来源注意力策略已更新", { policies: this._sourceFocusPolicies });
  }

  public registerTrigger(trigger: AttentionTrigger): void {
    this._triggers.set(trigger.id, trigger);
  }

  /** 查询指定频道的当前焦点状态（true = focused） */
  public getChannelFocused(channelId: string): boolean {
    return this._channelFocusStates.get(channelId) === true;
  }

  public unregisterTrigger(triggerId: string): void {
    this._triggers.delete(triggerId);
  }

  private ensureDefaultTriggers(): void {
    if (!this._triggers.has("wake-keyword-trigger")) {
      this.registerTrigger(new WakeKeywordTrigger());
    }
    // v4.5: 初始化记忆固化触发器
    if (!this._consolidationTrigger) {
      this._consolidationTrigger = new ConsolidationTrigger();
    }
  }

  private evaluateTriggers(content: string, sourceType: string): AttentionTriggerResult {
    for (const trigger of this._triggers.values()) {
      try {
        const result = trigger.evaluate({
          content,
          sourceType,
          summonKeywords: this._summonKeywords,
          focusOnAnyChat: this._focusOnAnyChat,
        });
        if (result.matched) {
          return result;
        }
      } catch (error) {
        logger.error('注意力触发器执行异常', {
          trigger_id: trigger.id,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
    return { matched: false };
  }
}
