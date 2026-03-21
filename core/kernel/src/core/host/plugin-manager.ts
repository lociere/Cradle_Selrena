/**
 * 插件管理器
 * 负责插件的加载、初始化、启动、停止、卸载、沙箱隔离、权限管控
 */
import path from "path";
import fs from "fs-extra";
import yaml from "yaml";
import {
  IBasePlugin,
  PluginManifest,
  PluginManifestSchema,
  Permission,
  PluginException,
  ErrorCode,
  PluginLoadedEvent,
  PluginStartedEvent,
  PluginStoppedEvent,
  PluginErrorEvent,
  createTraceContext,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../infrastructure/config/config-manager";
import { KernelProxyImpl } from "./bridge-impl/kernel-proxy-impl";
import { EventBus } from "../infrastructure/event-bus/event-bus";
import { getLogger } from "../infrastructure/logger/logger";
import { resolveRepoRoot } from "../infrastructure/utils/path-utils";

const logger = getLogger("plugin-manager");

/**
 * 插件实例包装类
 * 存储插件的完整信息、实例、代理、运行状态
 */
interface PluginInstance {
  manifest: PluginManifest;
  plugin: IBasePlugin;
  proxy: KernelProxyImpl;
  isRunning: boolean;
}

/**
 * 插件管理器
 * 单例模式
 */
export class PluginManager {
  private static _instance: PluginManager | null = null;
  private _pluginRootDir: string = path.resolve(process.cwd(), "plugins");
  private _plugins: Map<string, PluginInstance> = new Map();
  private _isInitialized: boolean = false;
  private _isShuttingDown: boolean = false;
  private _pluginTimeoutMs: number = 5000;

  /**
   * 获取单例实例
   */
  public static get instance(): PluginManager {
    if (!PluginManager._instance) {
      PluginManager._instance = new PluginManager();
    }
    return PluginManager._instance;
  }

  private constructor() {}

  /**
   * 初始化插件管理器，加载所有启用的插件
   */
  public async init(): Promise<void> {
    if (this._isInitialized) {
      logger.warn("插件管理器已初始化，跳过重复初始化");
      return;
    }

    logger.info("开始初始化插件管理器");
    const config = ConfigManager.instance.getConfig();
    // 插件根目录相对于仓库根（而非 process.cwd()），与 configs/kernel/plugin.yaml 的语义一致
    this._pluginRootDir = path.resolve(resolveRepoRoot(), config.plugin.plugin_root_dir);
    this._pluginTimeoutMs = config.plugin.sandbox.timeout_ms;

    try {
      // 确保插件根目录存在
      await fs.ensureDir(this._pluginRootDir);
      // 加载启用的插件列表
      const enabledPlugins = await ConfigManager.instance.loadEnabledPlugins();
      logger.info("读取到启用的插件列表", { enabled_plugins: enabledPlugins });

      // 按顺序加载所有启用的插件
      for (const pluginId of enabledPlugins) {
        if (this._isShuttingDown) break;
        try {
          await this.loadPlugin(pluginId);
        } catch (error) {
          logger.error("插件加载失败，已跳过", {
            plugin_id: pluginId,
            error: (error as Error).message,
          });
          await EventBus.instance.publish(
            new PluginErrorEvent(
              {
                pluginId,
                error: (error as Error).message,
                stack: (error as Error).stack,
              },
              createTraceContext()
            )
          );
        }
      }

      this._isInitialized = true;
      logger.info("插件管理器初始化完成", {
        total_enabled: enabledPlugins.length,
        successfully_loaded: this._plugins.size,
      });
    } catch (error) {
      logger.error("插件管理器初始化失败", { error: (error as Error).message });
      throw new PluginException(
        `插件管理器初始化失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_ERROR
      );
    }
  }

  /**
   * 加载单个插件
   * @param pluginId 插件ID（插件目录名称）
   */
  public async loadPlugin(pluginId: string): Promise<void> {
    if (this._plugins.has(pluginId)) {
      logger.warn("插件已加载，跳过重复加载", { plugin_id: pluginId });
      return;
    }

    const config = ConfigManager.instance.getConfig();
    const pluginDir = path.join(this._pluginRootDir, pluginId);
    logger.info("开始加载插件", { plugin_id: pluginId, plugin_dir: pluginDir });

    // 步骤1：校验插件目录是否存在
    if (!(await fs.pathExists(pluginDir))) {
      throw new PluginException(`插件目录不存在: ${pluginDir}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    // 步骤2：加载并校验插件清单文件
    const manifestPath = path.join(pluginDir, "plugin-manifest.yaml");
    if (!(await fs.pathExists(manifestPath))) {
      throw new PluginException(
        `插件清单文件不存在: ${manifestPath}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    let manifest: PluginManifest;
    try {
      const manifestContent = await fs.readFile(manifestPath, "utf-8");
      const parsedManifest = yaml.parse(manifestContent);
      const validationResult = PluginManifestSchema.safeParse(parsedManifest);
      if (!validationResult.success) {
        const errorDetails = validationResult.error.issues
          .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
          .join('; ');
        throw new Error(`清单格式校验失败: ${errorDetails}`);
      }
      manifest = validationResult.data;
    } catch (error) {
      throw new PluginException(
        `插件清单解析失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    // 步骤3：校验插件ID一致性
    if (manifest.id !== pluginId) {
      throw new PluginException(
        `插件ID不匹配，目录名: ${pluginId}, 清单ID: ${manifest.id}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    // 步骤4：校验插件是否在黑名单中
    if (config.plugin.plugin_blacklist.includes(pluginId)) {
      throw new PluginException(
        `插件在黑名单中，禁止加载: ${pluginId}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    // 步骤5：校验最小应用版本
    const appVersion = config.app.app_version;
    const minVersion = manifest.minAppVersion;
    if (!this.isVersionCompatible(appVersion, minVersion)) {
      throw new PluginException(
        `插件要求最低应用版本: ${minVersion}, 当前应用版本: ${appVersion}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    // 步骤6：合并权限，校验权限合法性
    const grantedPermissions: Permission[] = [
      ...(config.plugin.default_permissions as Permission[]),
      ...(manifest.permissions as Permission[]),
    ];
    logger.debug("插件权限合并完成", {
      plugin_id: pluginId,
      granted_permissions: grantedPermissions,
    });

    // 步骤7：创建内核代理实例
    const kernelProxy = new KernelProxyImpl(pluginId, grantedPermissions);

    // 步骤8：加载插件入口文件（使用原生 require）
    const entryPath = path.resolve(pluginDir, manifest.main);
    if (!(await fs.pathExists(entryPath))) {
      throw new PluginException(
        `插件入口文件不存在: ${entryPath}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    let pluginInstance: IBasePlugin;
    try {
      // 使用 Node.js 原生 require 加载插件
      // vm2 已官方弃用，后续可迁移到 worker_threads + MessageChannel 实现真正隔离
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const pluginExports = require(entryPath);
      const PluginClass = pluginExports.default || pluginExports.Plugin || pluginExports;
      if (!PluginClass || typeof PluginClass !== "function") {
        throw new Error("插件入口文件未导出插件类（需要 module.exports = PluginClass 或 exports.Plugin = PluginClass）");
      }

      pluginInstance = new PluginClass() as IBasePlugin;
      if (typeof pluginInstance.onInit !== "function" || typeof pluginInstance.onStart !== "function") {
        throw new Error("插件未实现必要的生命周期钩子: onInit/onStart");
      }

      pluginInstance.kernelProxy = kernelProxy;
    } catch (error) {
      throw new PluginException(
        `插件入口加载失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_SANDBOX_ERROR
      );
    }

    // 步骤9：执行插件生命周期钩子 preLoad
    if (typeof pluginInstance.preLoad === "function") {
      try {
        await this.withTimeout(
          pluginInstance.preLoad.bind(pluginInstance)(),
          this._pluginTimeoutMs,
          `插件 ${pluginId} preLoad 钩子执行超时`
        );
        logger.debug("插件preLoad钩子执行完成", { plugin_id: pluginId });
      } catch (error) {
        throw new PluginException(
          `插件preLoad钩子执行失败: ${(error as Error).message}`,
          ErrorCode.PLUGIN_LIFECYCLE_ERROR
        );
      }
    }

    // 步骤10：执行插件生命周期钩子 onInit
    try {
      await this.withTimeout(
        pluginInstance.onInit.bind(pluginInstance)(),
        this._pluginTimeoutMs,
        `插件 ${pluginId} onInit 钩子执行超时`
      );
      logger.debug("插件onInit钩子执行完成", { plugin_id: pluginId });
    } catch (error) {
      throw new PluginException(
        `插件onInit钩子执行失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_LIFECYCLE_ERROR
      );
    }

    // 步骤11：存储插件实例
    this._plugins.set(pluginId, {
      manifest,
      plugin: pluginInstance,
      proxy: kernelProxy,
      isRunning: false,
    });

    // 步骤12：发布插件加载完成事件
    await EventBus.instance.publish(
      new PluginLoadedEvent(
        {
          pluginId: manifest.id,
          pluginName: manifest.name,
          version: manifest.version,
        },
        createTraceContext()
      )
    );

    logger.info("插件加载成功", {
      plugin_id: pluginId,
      plugin_name: manifest.name,
      version: manifest.version,
      category: manifest.category,
    });
  }

  /**
   * 启动单个插件
   * @param pluginId 插件ID
   */
  public async startPlugin(pluginId: string): Promise<void> {
    const pluginInstance = this._plugins.get(pluginId);
    if (!pluginInstance) {
      throw new PluginException(`插件未加载，无法启动: ${pluginId}`, ErrorCode.PLUGIN_ERROR);
    }
    if (pluginInstance.isRunning) {
      logger.warn("插件已在运行中，跳过重复启动", { plugin_id: pluginId });
      return;
    }

    logger.info("开始启动插件", { plugin_id: pluginId });

    try {
      await this.withTimeout(
        pluginInstance.plugin.onStart.bind(pluginInstance.plugin)(),
        this._pluginTimeoutMs,
        `插件 ${pluginId} onStart 钩子执行超时`
      );

      pluginInstance.isRunning = true;
      this._plugins.set(pluginId, pluginInstance);

      await EventBus.instance.publish(
        new PluginStartedEvent(
          {
            pluginId: pluginInstance.manifest.id,
            pluginName: pluginInstance.manifest.name,
            version: pluginInstance.manifest.version,
          },
          createTraceContext()
        )
      );

      logger.info("插件启动成功", { plugin_id: pluginId });
    } catch (error) {
      logger.error("插件启动失败", { plugin_id: pluginId, error: (error as Error).message });
      throw new PluginException(
        `插件启动失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_LIFECYCLE_ERROR
      );
    }
  }

  /**
   * 启动所有已加载插件
   */
  public async startAllPlugins(): Promise<void> {
    for (const pluginId of this._plugins.keys()) {
      if (this._isShuttingDown) break;
      await this.startPlugin(pluginId);
    }
  }

  /**
   * 停止单个插件
   * @param pluginId 插件ID
   */
  public async stopPlugin(pluginId: string): Promise<void> {
    const pluginInstance = this._plugins.get(pluginId);
    if (!pluginInstance) {
      return;
    }
    if (!pluginInstance.isRunning) {
      return;
    }

    logger.info("开始停止插件", { plugin_id: pluginId });

    try {
      if (typeof pluginInstance.plugin.onStop === "function") {
        await this.withTimeout(
          pluginInstance.plugin.onStop.bind(pluginInstance.plugin)(),
          this._pluginTimeoutMs,
          `插件 ${pluginId} onStop 钩子执行超时`
        );
      }

      pluginInstance.isRunning = false;
      this._plugins.set(pluginId, pluginInstance);

      await EventBus.instance.publish(
        new PluginStoppedEvent(
          {
            pluginId: pluginInstance.manifest.id,
            pluginName: pluginInstance.manifest.name,
            version: pluginInstance.manifest.version,
          },
          createTraceContext()
        )
      );

      logger.info("插件停止成功", { plugin_id: pluginId });
    } catch (error) {
      logger.error("插件停止失败", { plugin_id: pluginId, error: (error as Error).message });
      throw new PluginException(
        `插件停止失败: ${(error as Error).message}`,
        ErrorCode.PLUGIN_LIFECYCLE_ERROR
      );
    }
  }

  /**
   * 停止所有插件
   */
  public async stopAllPlugins(): Promise<void> {
    for (const pluginId of Array.from(this._plugins.keys())) {
      if (this._isShuttingDown) break;
      await this.stopPlugin(pluginId);
    }
  }

  /**
   * 工具：执行带超时的 Promise
   */
  private async withTimeout<T>(promise: Promise<T>, timeoutMs: number, timeoutMessage: string): Promise<T> {
    let timeoutHandle: NodeJS.Timeout;
    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutHandle = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
    });

    return Promise.race([promise, timeoutPromise]).finally(() => {
      clearTimeout(timeoutHandle);
    });
  }

  /**
   * 关闭插件管理器，优雅停机
   */
  public async shutdown(): Promise<void> {
    if (this._isShuttingDown) {
      return;
    }

    logger.info("插件管理器开始关闭");
    this._isShuttingDown = true;

    // 停止所有插件
    await this.stopAllPlugins();
    // 清空所有插件实例
    this._plugins.clear();
    this._isInitialized = false;

    logger.info("插件管理器关闭完成");
  }

  /**
   * 版本兼容性检查，简单语义版本比较
   */
  private isVersionCompatible(current: string, minRequired: string): boolean {
    const parse = (v: string) => v.split(".").map((x) => parseInt(x, 10));
    const cur = parse(current);
    const min = parse(minRequired);
    for (let i = 0; i < Math.max(cur.length, min.length); i++) {
      const c = cur[i] ?? 0;
      const m = min[i] ?? 0;
      if (c > m) return true;
      if (c < m) return false;
    }
    return true;
  }
}
