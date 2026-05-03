/**
 * 应用根实例
 * 全项目生命周期总控，按顺序调度所有模块的启动/停止
 * 是整个内核的入口根节点
 */
import process from 'node:process';
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
import { initLogger, closeLogger, getLogger } from "./core/foundation/logger/logger";
import { ConfigManager } from "./core/foundation/config/config-manager";
import { EventBus } from "./core/foundation/event-bus/event-bus";
import { DBManager } from "./core/foundation/storage/db-manager";
import { MemoryRepository } from "./core/foundation/storage/repositories/memory-repository";
import { IPCServer } from "./core/infrastructure/ipc-broker/ipc-server";
import { PythonAIManager } from "./core/application/capabilities/inference/python-manager";
import { ExtensionManager } from "./core/host/extension-manager";
import { ExtensionHostAppService } from "./core/application/services/extension-host-app.service";
import { ActionStreamManager } from "./core/application/capabilities/action-stream/action-stream-manager";
import { VisualCommandDispatcher } from "./core/application/capabilities/action-stream/visual-command-dispatcher";
import { AvatarEngineController } from "./core/application/capabilities/avatar-engine/avatar-engine-controller";
import { DesktopUIController } from "./core/application/capabilities/desktop-ui/desktop-ui-controller";
import { AIProxy } from "./core/application/capabilities/inference/ai-proxy";
import { LifeClockManager } from "./core/domain/organism/life-clock/life-clock-manager";
import { MemorySyncManager } from "./core/application/capabilities/memory/memory-sync-manager";
import { AttentionSessionManager } from "./core/domain/attention/attention-session-manager";
import { PerceptionAppService } from "./core/application/services/perception-app.service";
import { SceneRoutingManager } from "./core/application/capabilities/scene/scene-routing-manager";
import { ExtensionSceneTranscriptService } from "./core/application/capabilities/scene/extension-scene-transcript-service";
import { AudioService } from "./core/application/capabilities/audio/audio-service";
import { ChannelRuntimeManager } from "./core/application/channel/ChannelRuntimeManager";
import { IngressGateManager } from "./core/foundation/ingress-gate/ingress-gate-manager";

const logger = getLogger("app-root");

/**
 * 应用根实例
 * 单例模式
 */
export class App {
  private static _instance: App | null = null;
  private _state: AppLifecycleState = AppLifecycleState.UNINITIALIZED;
  private _startupTimeMs: number = 0;
  private _extensionManager: ExtensionManager | null = null;

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
      // 步骤1.5：初始化入站防护
      // ======================================
      IngressGateManager.instance.init(globalConfig.system.ingress_gate);
      logger.info("入站防护已初始化");

      // ======================================
      // 步骤2：初始化全局日志器
      // ======================================
      initLogger(globalConfig.system);
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
      // 步骤6：初始化扩展管理器，加载扩展
      // ======================================
      const extensionStart = Date.now();
      const perceptionAppService = new PerceptionAppService(
        SceneRoutingManager.instance,
        ExtensionSceneTranscriptService.instance,
        AudioService.instance,
        ChannelRuntimeManager.instance,
        AttentionSessionManager.instance
      );
      const extensionHostService = new ExtensionHostAppService(perceptionAppService);
      const extensionManager = new ExtensionManager(extensionHostService);
      this._extensionManager = extensionManager;
      await extensionManager.init();
      await extensionManager.startAllExtensions();
      const extensionStartupTime = Date.now() - extensionStart;
      await EventBus.instance.publish(
        new ModuleStartedEvent({
          moduleName: "extension-manager",
          startupTimeMs: extensionStartupTime,
        }, rootTraceContext)
      );
      logger.info("扩展管理器启动完成", { startup_time_ms: extensionStartupTime });

      // ======================================
      // 步骤7：初始化动作流管理器
      // ======================================
      ActionStreamManager.instance.init();
      VisualCommandDispatcher.instance.init();

      // 原生整合：初始化 Avatar引擎 与 Desktop UI 引擎
      if (globalConfig.system.renderer.avatar_shell.enabled) {
        AvatarEngineController.instance.init(globalConfig.system.renderer.avatar_shell);
        logger.info("AvatarEngine 启动完成", {
          port: globalConfig.system.renderer.avatar_shell.port,
        });
      } else {
        logger.info("AvatarEngine 已禁用");
      }

      if (globalConfig.system.renderer.desktop_shell.enabled) {
        DesktopUIController.instance.init(
          perceptionAppService,
          globalConfig.system.renderer.desktop_shell,
        );
        logger.info("DesktopUIEngine 启动完成", {
          port: globalConfig.system.renderer.desktop_shell.port,
        });
      } else {
        logger.info("DesktopUIEngine 已禁用");
      }

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
      AttentionSessionManager.instance.init(AIProxy.instance, ActionStreamManager.instance);
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
      await LifeClockManager.instance.init(AIProxy.instance);
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

      // 所有模块就绪 → 开放入站防护
      IngressGateManager.instance.setSystemReady(true);

      await EventBus.instance.publish(new AppStartedEvent({
        startupTimeMs: this._startupTimeMs,
      }, rootTraceContext));

      logger.info("应用启动完成！月见已醒来", {
        total_startup_time_ms: this._startupTimeMs,
        app_name: globalConfig.system.app_name,
        app_version: globalConfig.system.app_version,
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

    // 立即关闭入站防护，拒绝新输入
    IngressGateManager.instance.setSystemReady(false);

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
      await AttentionSessionManager.instance.stop();
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "attention-session",
      }, stopTraceContext));
      logger.info("注意力会话管理器已停止");

      // 3. 停止动作流管理器
      ActionStreamManager.instance.stop();
      VisualCommandDispatcher.instance.stop();

      // 3.5 停止原生引擎
      AvatarEngineController.instance.stop();
      DesktopUIController.instance.stop();
      logger.info("原生引擎已停止");
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "action-stream",
      }, stopTraceContext));
      logger.info("动作流管理器已停止");

      // 4. 停止扩展管理器
      if (this._extensionManager) {
        await this._extensionManager.shutdown();
      }
      await EventBus.instance.publish(new ModuleStoppedEvent({
        moduleName: "extension-manager",
      }, stopTraceContext));
      logger.info("扩展管理器已停止");

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

      // 9. 关闭入站防护
      IngressGateManager.instance.stop();
      logger.info("入站防护已停止");

      // 10. 关闭事件总线
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

