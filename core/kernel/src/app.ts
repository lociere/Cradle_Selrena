/**
 * 应用根实例
 * 全项目生命周期总控，按顺序调度所有模块的启动/停止
 * 是整个内核的入口根节点
 */
import {
  createTraceContext,
  AppStartingEvent,
  AppStartedEvent,
  AppStoppingEvent,
  AppStoppedEvent,
  ModuleStartedEvent,
  ModuleStoppedEvent,
  CoreException,
  ErrorCode,
} from "@cradle-selrena/protocol";
import { AppLifecycleState } from "./core/lifecycle/lifecycle-state.enum";
import { initLogger, closeLogger, getLogger } from "./core/infrastructure/logger/logger";
import { ConfigManager } from "./core/infrastructure/config/config-manager";
import { EventBus } from "./core/infrastructure/event-bus/event-bus";
import { DBManager } from "./core/infrastructure/storage/db-manager";
import { MemoryRepository } from "./core/infrastructure/storage/repositories/memory-repository";
import { IPCServer } from "./core/infrastructure/ipc-broker/ipc-server";
import { PythonAIManager } from "./core/application/capabilities/inference/python-manager";
import { PluginManager } from "./core/host/plugin-manager";
import { ActionStreamManager } from "./core/application/capabilities/action-stream/action-stream-manager";
import { LifeClockManager } from "./core/domain/organism/life-clock/life-clock-manager";
import { MemorySyncManager } from "./core/application/capabilities/memory/memory-sync-manager";
import { AttentionSessionManager } from "./core/domain/attention/attention-session-manager";

const logger = getLogger("app-root");

/**
 * 应用根实例
 * 单例模式
 */
export class App {
  private static _instance: App | null = null;
  private _state: AppLifecycleState = AppLifecycleState.UNINITIALIZED;
  private _startupTimeMs: number = 0;

  /**
   * 获取单例实例
   */
  public static get instance(): App {
    if (!App._instance) {
      App._instance = new App();
    }
    return App._instance;
  }

  private constructor() {}

  /**
   * 获取当前应用生命周期状态
   */
  public get state(): AppLifecycleState {
    return this._state;
  }

  /**
   * 应用启动入口
   * 严格按架构定义的模块启动顺序执行
   */
  public async start(): Promise<void> {
    if (this._state !== AppLifecycleState.UNINITIALIZED && this._state !== AppLifecycleState.STOPPED) {
      logger.warn("应用已在启动/运行中，跳过重复启动", { current_state: this._state });
      return;
    }

    const appStartTime = Date.now();
    this._state = AppLifecycleState.INITIALIZING;
    const rootTraceContext = createTraceContext();

    try {
      logger.info("应用开始启动", { trace_id: rootTraceContext.trace_id });
      await EventBus.instance.publish(
        new AppStartingEvent({ appVersion: "1.0.0" }, rootTraceContext)
      );

      // ======================================
      // 步骤1：初始化配置管理器
      // ======================================
      const configStart = Date.now();
      await ConfigManager.instance.init();
      const globalConfig = ConfigManager.instance.getConfig();
      const moduleStartupTime = Date.now() - configStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "config",
          startupTimeMs: moduleStartupTime,
        }, rootTraceContext)
      );
      logger.info("配置管理器启动完成", { startup_time_ms: moduleStartupTime });

      // ======================================
      // 步骤2：初始化全局日志器
      // ======================================
      initLogger(globalConfig.app);
      logger.info("全局日志器初始化完成");

      // ======================================
      // 步骤3：初始化持久化数据库
      // ======================================
      const dbStart = Date.now();
      await DBManager.instance.init();
      // 初始化记忆仓库
      MemoryRepository.instance;
      await MemorySyncManager.instance.init();
      const dbStartupTime = Date.now() - dbStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "persistence",
          startupTimeMs: dbStartupTime,
        }, rootTraceContext)
      );
      logger.info("持久化层启动完成", { startup_time_ms: dbStartupTime });

      // ======================================
      // 步骤4：启动IPC通信服务端
      // ======================================
      const ipcStart = Date.now();
      await IPCServer.instance.start();
      const ipcStartupTime = Date.now() - ipcStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "ipc-server",
          startupTimeMs: ipcStartupTime,
        }, rootTraceContext)
      );
      logger.info("IPC服务端启动完成", { startup_time_ms: ipcStartupTime });

      // ======================================
      // 步骤5：启动Python AI层
      // ======================================
      const aiStart = Date.now();
      await PythonAIManager.instance.start();
      const aiStartupTime = Date.now() - aiStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "python-ai-core",
          startupTimeMs: aiStartupTime,
        }, rootTraceContext)
      );
      logger.info("Python AI层启动完成", { startup_time_ms: aiStartupTime });

      // ======================================
      // 步骤6：初始化插件管理器，加载插件
      // ======================================
      const pluginStart = Date.now();
      await PluginManager.instance.init();
      await PluginManager.instance.startAllPlugins();
      const pluginStartupTime = Date.now() - pluginStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "plugin-manager",
          startupTimeMs: pluginStartupTime,
        }, rootTraceContext)
      );
      logger.info("插件管理器启动完成", { startup_time_ms: pluginStartupTime });

      // ======================================
      // 步骤7：初始化动作流管理器
      // ======================================
      ActionStreamManager.instance.init();
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "action-stream",
          startupTimeMs: 0,
        }, rootTraceContext)
      );
      logger.info("动作流管理器启动完成");

      // ======================================
      // 步骤8：初始化注意力会话管理器
      // ======================================
      AttentionSessionManager.instance.init();
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "attention-session",
          startupTimeMs: 0,
        }, rootTraceContext)
      );
      logger.info("注意力会话管理器启动完成");

      // ======================================
      // 步骤9：启动生命时钟
      // ======================================
      const clockStart = Date.now();
      await LifeClockManager.instance.init();
      LifeClockManager.instance.start();
      const clockStartupTime = Date.now() - clockStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "life-clock",
          startupTimeMs: clockStartupTime,
        }, rootTraceContext)
      );
      logger.info("生命时钟启动完成", { startup_time_ms: clockStartupTime });

      // ======================================
      // 启动完成
      // ======================================
      this._startupTimeMs = Date.now() - appStartTime;
      this._state = AppLifecycleState.RUNNING;

      await EventBus.instance.publish(new AppStartedEvent({
        startupTimeMs: this._startupTimeMs,
      }, rootTraceContext));

      logger.info("应用启动完成！月见已醒来", {
        total_startup_time_ms: this._startupTimeMs,
        app_name: globalConfig.app.app_name,
        app_version: globalConfig.app.app_version,
      });

    } catch (error) {
      logger.critical("应用启动失败", {
        error: (error as Error).message,
        stack: (error as Error).stack,
        trace_id: rootTraceContext.trace_id,
      });
      this._state = AppLifecycleState.ERROR;
      // 优雅停机，释放已启动的资源
      await this.stop();
      throw new CoreException(
        `应用启动失败: ${(error as Error).message}`,
        ErrorCode.LIFECYCLE_ERROR,
        rootTraceContext.trace_id
      );
    }
  }

  /**
   * 应用停止入口
   * 严格按启动顺序的逆序执行停机
   */
  public async stop(exitCode: number = 0): Promise<void> {
    if (this._state === AppLifecycleState.STOPPING || this._state === AppLifecycleState.STOPPED) {
      return;
    }

    const stopTraceContext = createTraceContext();
    logger.info("应用开始停止", {
      current_state: this._state,
      exit_code: exitCode,
      trace_id: stopTraceContext.trace_id,
    });

    this._state = AppLifecycleState.STOPPING;
    await EventBus.instance.publish(new AppStoppingEvent({
      reason: exitCode === 0 ? "正常停机" : "异常停机",
    }, stopTraceContext));

    try {
      // 严格按逆序停止模块
      // 1. 停止生命时钟
      LifeClockManager.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "life-clock",
      }, stopTraceContext));
      logger.info("生命时钟已停止");

      // 2. 停止注意力会话管理器
      AttentionSessionManager.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "attention-session",
      }, stopTraceContext));
      logger.info("注意力会话管理器已停止");

      // 3. 停止动作流管理器
      ActionStreamManager.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "action-stream",
      }, stopTraceContext));
      logger.info("动作流管理器已停止");

      // 4. 停止插件管理器
      await PluginManager.instance.shutdown();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "plugin-manager",
      }, stopTraceContext));
      logger.info("插件管理器已停止");

      // 5. 停止Python AI层
      await PythonAIManager.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "python-ai-core",
      }, stopTraceContext));
      logger.info("Python AI层已停止");

      // 6. 停止记忆同步管理器
      await MemorySyncManager.instance.shutdown();
      logger.info("记忆同步管理器已停止");

      // 7. 停止IPC服务端
      await IPCServer.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "ipc-server",
      }, stopTraceContext));
      logger.info("IPC服务端已停止");

      // 8. 关闭数据库连接
      await DBManager.instance.close();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "persistence",
      }, stopTraceContext));
      logger.info("数据库已关闭");

      // 9. 关闭事件总线
      await EventBus.instance.shutdown();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "event-bus",
      }, stopTraceContext));
      logger.info("事件总线已关闭");

      // 10. 关闭日志器
      await closeLogger();

      this._state = AppLifecycleState.STOPPED;
      await EventBus.instance.publish(new AppStoppedEvent({
        exitCode: exitCode,
      }, stopTraceContext));

      console.log("应用已优雅停止");
      process.exit(exitCode);

    } catch (error) {
      console.error("应用停机过程中发生异常", error);
      process.exit(1);
    }
  }
}
