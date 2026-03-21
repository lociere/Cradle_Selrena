/**
 * 生命时钟管理器
 * 驱动月见的主动思维，实现「活着」的核心特性
 * 按配置的间隔发送心跳给Python AI层，触发主动思维生成
 */
import { ConfigManager } from "../../../infrastructure/config/config-manager";
import { AIProxy } from "../../../application/capabilities/inference/ai-proxy";
import { getLogger } from "../../../infrastructure/logger/logger";
import { AttentionTrigger, AttentionTriggerResult } from "./triggers/attention-trigger";
import { WakeKeywordTrigger } from "./triggers/wake-keyword-trigger";

const logger = getLogger("life-clock-manager");

export type AttentionMode = "standby" | "ambient" | "focused";
type SourceAttentionPolicy =
  | "always_focused"
  | "wake_word_focus"
  | "wake_word_focus_with_timeout"
  | "chat_or_wake_focus_with_timeout"
  | "ignore";

/**
 * 生命时钟管理器
 * 单例模式
 */
export class LifeClockManager {
  private static _instance: LifeClockManager | null = null;
  private _timer: NodeJS.Timeout | null = null;
  private _focusResetTimer: NodeJS.Timeout | null = null;
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
  private _stickyFocusSource: string | null = null;
  private _sourceFocusPolicies: Record<string, SourceAttentionPolicy> = {
    private: "always_focused",
    group: "wake_word_focus_with_timeout",
    channel: "wake_word_focus_with_timeout",
    terminal: "chat_or_wake_focus_with_timeout",
    system: "ignore",
    unknown: "chat_or_wake_focus_with_timeout",
  };
  private readonly _triggers: Map<string, AttentionTrigger> = new Map();

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
  public async init(): Promise<void> {
    const config = ConfigManager.instance.getConfig();
    const lifeClock = config.ai.inference.life_clock;
    this._focusedIntervalMs = lifeClock.focused_interval_ms;
    this._ambientIntervalMs = lifeClock.ambient_interval_ms;
    this._defaultMode = lifeClock.default_mode;
    this._mode = this._defaultMode;
    this._focusDurationMs = lifeClock.focus_duration_ms;
    this._focusOnAnyChat = lifeClock.focus_on_any_chat;
    this._summonKeywords = lifeClock.summon_keywords;
    this._activeThoughtModes = new Set(lifeClock.active_thought_modes);
    this._heartbeatEnabled = this._activeThoughtModes.size > 0;
    this._sourceFocusPolicies = {
      ...this._sourceFocusPolicies,
      ...(lifeClock.source_focus_policies || {}),
    };
    this.ensureDefaultTriggers();

    logger.info("生命时钟管理器初始化完成", {
      focused_interval_ms: this._focusedIntervalMs,
      ambient_interval_ms: this._ambientIntervalMs,
      default_mode: this._defaultMode,
      focus_duration_ms: this._focusDurationMs,
      focus_on_any_chat: this._focusOnAnyChat,
      summon_keywords: this._summonKeywords,
      source_focus_policies: this._sourceFocusPolicies,
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
   */
  private startHeartbeatLoop(): void {
    if (!this._isRunning) return;

    const interval = this._mode === "focused" ? this._focusedIntervalMs : this._ambientIntervalMs;

    this._timer = setTimeout(async () => {
      if (!this._isRunning) return;

      try {
        // 检查Python AI层是否就绪
        if (!AIProxy.instance.isReady) {
          logger.warn("Python AI层未就绪，跳过本次心跳");
          return;
        }

        // 仅在允许主动思维的模式下触发生命心跳
        if (!this._activeThoughtModes.has(this._mode)) {
          logger.debug("当前模式不触发主动思维，跳过心跳", { mode: this._mode });
          return;
        }

        // 发送生命心跳，触发主动思维
        await AIProxy.instance.sendLifeHeartbeat({ attention_mode: this._mode });
      } catch (error) {
        logger.error("生命心跳执行异常", { error: (error as Error).message });
      } finally {
        // 继续下一次循环
        this.startHeartbeatLoop();
      }
    }, interval);
  }

  /**
   * 消息触发注意力状态变化：支持“呼唤后聚焦”与“任意聊天聚焦”两种策略
   */
  public onUserMessage(content: string, sourceType: string = "unknown"): void {
    if (!this._isRunning || !this._heartbeatEnabled) return;
    const normalized = String(content || "");
    const normalizedSource = String(sourceType || "unknown").toLowerCase();
    const policy = this.resolveSourcePolicy(normalizedSource);
    const trigger = this.evaluateTriggers(normalized, normalizedSource);

    if (policy === "ignore") {
      return;
    }

    if (policy === "always_focused") {
      this._stickyFocusSource = normalizedSource;
      this.setMode("focused", `${normalizedSource}_always_focus`);
      this.clearFocusResetTimer();
      return;
    }

    if (this._stickyFocusSource && this._stickyFocusSource !== normalizedSource) {
      this._stickyFocusSource = null;
      if (this._mode === "focused") {
        this.setMode(this._defaultMode, "leave_sticky_focus");
      }
    }

    if (policy === "wake_word_focus") {
      if (trigger.matched) {
        this.setMode("focused", `${normalizedSource}_${trigger.reason || "trigger"}`);
        this.clearFocusResetTimer();
      }
      return;
    }

    if (policy === "wake_word_focus_with_timeout") {
      if (trigger.matched) {
        this.setMode("focused", `${normalizedSource}_${trigger.reason || "trigger"}`);
      }
      return;
    }

    if (trigger.matched) {
      this.setMode("focused", trigger.reason || "trigger");
      return;
    }

    if (this._mode === "focused" && !this._stickyFocusSource) {
      this.scheduleFocusReset();
    }
  }

  /**
   * 手动切换注意力模式
   */
  public setMode(mode: AttentionMode, reason: string = "manual"): void {
    if (this._mode === mode) {
      if (mode === "focused" && !this._stickyFocusSource) {
        this.scheduleFocusReset();
      }
      return;
    }

    const prev = this._mode;
    this._mode = mode;
    logger.info("注意力模式切换", { from: prev, to: mode, reason });

    if (mode === "focused") {
      if (this._stickyFocusSource) {
        this.clearFocusResetTimer();
      } else {
        this.scheduleFocusReset();
      }
    } else {
      this._stickyFocusSource = null;
      this.clearFocusResetTimer();
    }

    this.restartLoop();
  }

  private scheduleFocusReset(): void {
    this.clearFocusResetTimer();
    this._focusResetTimer = setTimeout(() => {
      if (!this._isRunning || this._mode !== "focused") return;
      this.setMode(this._defaultMode, "focus_timeout");
    }, this._focusDurationMs);
  }

  private clearFocusResetTimer(): void {
    if (this._focusResetTimer) {
      clearTimeout(this._focusResetTimer);
      this._focusResetTimer = null;
    }
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
   * 获取当前时钟状态
   */
  public get state(): { isRunning: boolean; mode: AttentionMode } {
    return {
      isRunning: this._isRunning,
      mode: this._mode,
    };
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
    this._stickyFocusSource = null;
    this.clearFocusResetTimer();
  }

  private resolveSourcePolicy(sourceType: string): SourceAttentionPolicy {
    const policy = this._sourceFocusPolicies[sourceType] || this._sourceFocusPolicies.unknown;
    if (!policy) {
      return "chat_or_wake_focus_with_timeout";
    }
    return policy;
  }

  public registerTrigger(trigger: AttentionTrigger): void {
    this._triggers.set(trigger.id, trigger);
  }

  public unregisterTrigger(triggerId: string): void {
    this._triggers.delete(triggerId);
  }

  private ensureDefaultTriggers(): void {
    if (!this._triggers.has("wake-keyword-trigger")) {
      this.registerTrigger(new WakeKeywordTrigger());
    }
  }

  private evaluateTriggers(content: string, sourceType: string): AttentionTriggerResult {
    for (const trigger of this._triggers.values()) {
      const result = trigger.evaluate({
        content,
        sourceType,
        summonKeywords: this._summonKeywords,
        focusOnAnyChat: this._focusOnAnyChat,
      });
      if (result.matched) {
        return result;
      }
    }
    return { matched: false };
  }
}
