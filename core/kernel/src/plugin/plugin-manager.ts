/**
 * 插件管理器
 * 负责插件的加载、初始化、启动、停止、卸载、沙箱隔离、权限管控
 */
import path from "path";
import fs from "fs-extra";
import yaml from "yaml";
import { VM } from "vm2";
import { EventBus } from "../event-bus/event-bus";
import { ConfigManager } from "../config/config-manager";
import { getLogger } from "../observability/logger";
import { CoreException } from "@cradle-selrena/protocol";

const logger = getLogger("plugin-manager");

interface PluginInstance {
  manifest: any;
  plugin: any;
  proxy: any;
  isRunning: boolean;
}

export class PluginManager {
  private static _instance: PluginManager | null = null;
  private _pluginRootDir: string = path.resolve(process.cwd(), "plugins");
  private _plugins: Map<string, PluginInstance> = new Map();
  private _isInitialized: boolean = false;
  private _isShuttingDown: boolean = false;
  private _pluginTimeoutMs: number = 5000;

  public static get instance(): PluginManager {
    if (!PluginManager._instance) PluginManager._instance = new PluginManager();
    return PluginManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._isInitialized) {
      logger.warn("插件管理器已初始化，跳过重复初始化");
      return;
    }

    logger.info("开始初始化插件管理器");
    const config = ConfigManager.instance.getConfig();
    this._pluginRootDir = path.resolve(process.cwd(), config.plugin.plugin_root_dir || "plugins");
    this._pluginTimeoutMs = config.plugin.sandbox?.timeout_ms || this._pluginTimeoutMs;

    try {
      await fs.ensureDir(this._pluginRootDir);
      const enabledPlugins = await ConfigManager.instance.loadEnabledPlugins();
      logger.info("读取到启用的插件列表", { enabled_plugins: enabledPlugins });
      for (const pluginId of enabledPlugins) {
        if (this._isShuttingDown) break;
        try {
          await this.loadPlugin(pluginId);
        } catch (error) {
          logger.error("插件加载失败，已跳过", { plugin_id: pluginId, error: (error as Error).message });
        }
      }
      this._isInitialized = true;
      logger.info("插件管理器初始化完成", { total_enabled: enabledPlugins.length, successfully_loaded: this._plugins.size });
    } catch (error) {
      logger.error("插件管理器初始化失败", { error: (error as Error).message });
      throw new CoreException(`插件管理器初始化失败: ${(error as Error).message}`);
    }
  }

  public async loadPlugin(pluginId: string): Promise<void> {
    if (this._plugins.has(pluginId)) {
      logger.warn("插件已加载，跳过重复加载", { plugin_id: pluginId });
      return;
    }

    const config = ConfigManager.instance.getConfig();
    const pluginDir = path.join(this._pluginRootDir, pluginId);
    logger.info("开始加载插件", { plugin_id: pluginId, plugin_dir: pluginDir });

    if (!await fs.pathExists(pluginDir)) {
      throw new CoreException(`插件目录不存在: ${pluginDir}`);
    }

    const manifestPath = path.join(pluginDir, "plugin-manifest.yaml");
    if (!await fs.pathExists(manifestPath)) {
      throw new CoreException(`插件清单文件不存在: ${manifestPath}`);
    }

    let manifest: any;
    try {
      const manifestContent = await fs.readFile(manifestPath, "utf-8");
      manifest = yaml.parse(manifestContent);
    } catch (error) {
      throw new CoreException(`插件清单解析失败: ${(error as Error).message}`);
    }

    if (manifest.id !== pluginId) {
      throw new CoreException(`插件ID不匹配，目录名: ${pluginId}, 清单ID: ${manifest.id}`);
    }

    if (config.plugin.plugin_blacklist?.includes(pluginId)) {
      throw new CoreException(`插件在黑名单中，禁止加载: ${pluginId}`);
    }

    const grantedPermissions = [ ...(config.plugin.default_permissions || []), ...(manifest.permissions || []) ];
    logger.debug("插件权限合并完成", { plugin_id: pluginId, granted_permissions: grantedPermissions });

    const kernelProxy = { pluginId, permissions: grantedPermissions } as any;

    const entryPath = path.resolve(pluginDir, manifest.main || "index.js");
    if (!await fs.pathExists(entryPath)) {
      throw new CoreException(`插件入口文件不存在: ${entryPath}`);
    }

    let pluginInstance: any;
    try {
      const vm = new VM({ timeout: this._pluginTimeoutMs, sandbox: {}, require: false } as any);
      const entryCode = await fs.readFile(entryPath, "utf-8");
      const pluginExports = vm.run(entryCode, entryPath);
      const PluginClass = pluginExports.default || pluginExports.Plugin;
      if (!PluginClass) throw new Error("插件入口文件未导出默认插件类");
      pluginInstance = new PluginClass();
      if (typeof pluginInstance.onInit !== "function" || typeof pluginInstance.onStart !== "function") throw new Error("插件未实现必要的生命周期钩子: onInit/onStart");
      pluginInstance.kernelProxy = kernelProxy;
    } catch (error) {
      throw new CoreException(`插件入口加载失败: ${(error as Error).message}`);
    }

    if (typeof pluginInstance.preLoad === "function") {
      try {
        await Promise.race([ pluginInstance.preLoad.bind(pluginInstance)(), new Promise((_, r) => setTimeout(() => r(new Error("preLoad 超时")), this._pluginTimeoutMs)) ]);
        logger.debug("插件preLoad钩子执行完成", { plugin_id: pluginId });
      } catch (error) {
        throw new CoreException(`插件preLoad钩子执行失败: ${(error as Error).message}`);
      }
    }

    try {
      await Promise.race([ pluginInstance.onInit.bind(pluginInstance)(), new Promise((_, r) => setTimeout(() => r(new Error("onInit 超时")), this._pluginTimeoutMs)) ]);
      logger.debug("插件onInit钩子执行完成", { plugin_id: pluginId });
    } catch (error) {
      throw new CoreException(`插件onInit钩子执行失败: ${(error as Error).message}`);
    }

    this._plugins.set(pluginId, { manifest, plugin: pluginInstance, proxy: kernelProxy, isRunning: false });

    // 发布插件加载事件（简单实现：通过 EventBus 发布字符串事件）
    try { await EventBus.instance.publish({ event_type: "plugin.loaded", event_id: `${pluginId}:loaded`, trace_context: { trace_id: "" }, payload: { pluginId: manifest.id, name: manifest.name } } as any); } catch {}

    logger.info("插件加载成功", { plugin_id: pluginId, plugin_name: manifest.name, version: manifest.version, category: manifest.category });
  }

  public async startPlugin(pluginId: string): Promise<void> {
    const pluginInstance = this._plugins.get(pluginId);
    if (!pluginInstance) throw new CoreException(`插件未加载，无法启动: ${pluginId}`);
    if (pluginInstance.isRunning) {
      logger.warn("插件已在运行中，跳过重复启动", { plugin_id: pluginId });
      return;
    }
    logger.info("开始启动插件", { plugin_id: pluginId });
    try {
      await Promise.race([ pluginInstance.plugin.onStart.bind(pluginInstance.plugin)(), new Promise((_, r) => setTimeout(() => r(new Error("onStart 超时")), this._pluginTimeoutMs)) ]);
      pluginInstance.isRunning = true;
      this._plugins.set(pluginId, pluginInstance);
      try { await EventBus.instance.publish({ event_type: "plugin.started", event_id: `${pluginId}:started`, trace_context: { trace_id: "" }, payload: { pluginId } } as any); } catch {}
      logger.info("插件启动成功", { plugin_id: pluginId });
    } catch (error) {
      logger.error("插件启动失败", { plugin_id: pluginId, error: (error as Error).message });
      try { await EventBus.instance.publish({ event_type: "plugin.error", event_id: `${pluginId}:error`, trace_context: { trace_id: "" }, payload: { pluginId, error: (error as Error).message } } as any); } catch {}
      throw new CoreException(`插件启动失败: ${(error as Error).message}`);
    }
  }

  public async startAllPlugins(): Promise<void> {
    logger.info("开始启动所有已加载的插件");
    const pluginIds = Array.from(this._plugins.keys());
    let successCount = 0;
    for (const pluginId of pluginIds) {
      if (this._isShuttingDown) break;
      try { await this.startPlugin(pluginId); successCount++; } catch (error) { logger.error("插件启动失败，已跳过", { plugin_id: pluginId, error: (error as Error).message }); }
    }
    logger.info("所有插件启动完成", { total: pluginIds.length, success: successCount, failed: pluginIds.length - successCount });
  }
}
