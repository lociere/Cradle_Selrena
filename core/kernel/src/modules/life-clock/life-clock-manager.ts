/**
 * 生命时钟管理器
 * 驱动月见的主动思维，实现「活着」的核心特性
 * 按配置的间隔发送心跳给Python AI层，触发主动思维生成
 */
import { ConfigManager } from "../../core/config/config-manager";
import { AIProxy } from "../ai/ai-proxy";
import { getLogger } from "../../core/observability/logger";

const logger = getLogger("life-clock-manager");

/**
 * 生命时钟管理器
 * 单例模式
 */
export class LifeClockManager {
  private static _instance: LifeClockManager | null = null;
  private _timer: NodeJS.Timeout | null = null;
  private _isRunning: boolean = false;
  private _isSleeping: boolean = false;
  private _thoughtIntervalMs: number = 10000;
  private _sleepIntervalMs: number = 60000;

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
    this._thoughtIntervalMs = config.ai.inference.life_clock.thought_interval_ms;
    this._sleepIntervalMs = config.ai.inference.life_clock.sleep_interval_ms;

    logger.info("生命时钟管理器初始化完成", {
      thought_interval_ms: this._thoughtIntervalMs,
      sleep_interval_ms: this._sleepIntervalMs,
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
    this._isSleeping = false;
    this.startHeartbeatLoop();
  }

  /**
   * 启动心跳循环
   */
  private startHeartbeatLoop(): void {
    if (!this._isRunning) return;

    const interval = this._isSleeping ? this._sleepIntervalMs : this._thoughtIntervalMs;

    this._timer = setTimeout(async () => {
      if (!this._isRunning) return;

      try {
        // 检查Python AI层是否就绪
        if (!AIProxy.instance.isReady) {
          logger.warn("Python AI层未就绪，跳过本次心跳");
          return;
        }

        // 发送生命心跳，触发主动思维
        await AIProxy.instance.sendLifeHeartbeat();
      } catch (error) {
        logger.error("生命心跳执行异常", { error: (error as Error).message });
      } finally {
        // 继续下一次循环
        this.startHeartbeatLoop();
      }
    }, interval);
  }

  /**
   * 进入休眠状态，降低心跳频率
   */
  public sleep(): void {
    if (this._isSleeping) return;
    logger.info("生命时钟进入休眠状态");
    this._isSleeping = true;
    this.restartLoop();
  }

  /**
   * 唤醒，恢复正常心跳频率
   */
  public wakeUp(): void {
    if (!this._isSleeping) return;
    logger.info("生命时钟已唤醒");
    this._isSleeping = false;
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
   * 获取当前时钟状态
   */
  public get state(): { isRunning: boolean; isSleeping: boolean } {
    return {
      isRunning: this._isRunning,
      isSleeping: this._isSleeping,
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
  }
}
