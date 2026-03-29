import path from "path";
import fs from "fs-extra";
import yaml from "yaml";
import {
  IPluginHostService,
  IDisposable,
  IPluginLogger,
  ExtensionContext,
  SystemPlugin,
  Permission,
  hasPermission,
  PluginManifestSchema,
  PluginManifest,
  PluginLoadedEvent,
  PluginStartedEvent,
  PluginStoppedEvent,
  PluginErrorEvent,
  PluginException,
  ErrorCode,
  createTraceContext,
  PluginSystemEventTopics,
} from "@cradle-selrena/protocol";

type PluginManifestLite = {
  id: string;
  name: string;
  version: string;
  main: string;
  minAppVersion: string;
  permissions: Permission[];
};

interface PluginInstance {
  manifest: PluginManifestLite;
  plugin: SystemPlugin;
  context: ExtensionContext;
  isRunning: boolean;
}

const PLUGIN_SUBSCRIBE_TOPICS = new Set<string>(Object.values(PluginSystemEventTopics));

export class PluginManager {
  private _pluginRootDir: string = path.resolve(process.cwd(), "plugins");
  private _plugins: Map<string, PluginInstance> = new Map();
  private _isInitialized = false;
  private _isShuttingDown = false;
  private _pluginTimeoutMs = 5000;
  private readonly _logger: IPluginLogger;

  constructor(private readonly _hostService: IPluginHostService) {
    this._logger = _hostService.createLogger("plugin-manager");
  }

  public async init(): Promise<void> {
    if (this._isInitialized) {
      this._logger.warn("插件管理器已初始化，跳过重复初始化");
      return;
    }

    const config = this._hostService.getConfig();
    this._pluginRootDir = path.resolve(this._hostService.getRepoRoot(), config.plugin.plugin_root_dir);
    this._pluginTimeoutMs = config.plugin.sandbox.timeout_ms;

    await fs.ensureDir(this._pluginRootDir);
    const enabledPlugins = await this._hostService.loadEnabledPlugins();
    this._logger.info("读取到启用的插件列表", { enabled_plugins: enabledPlugins });

    for (const pluginId of enabledPlugins) {
      if (this._isShuttingDown) break;
      try {
        await this.loadPlugin(pluginId);
      } catch (error) {
        const message = (error as Error).message;
        this._logger.error("插件加载失败，已跳过", { plugin_id: pluginId, error: message });
        this._hostService.publishDomainEvent(
          new PluginErrorEvent(
            {
              pluginId,
              error: message,
              stack: (error as Error).stack,
            },
            createTraceContext()
          )
        );
      }
    }

    this._isInitialized = true;
    this._logger.info("插件管理器初始化完成", {
      total_enabled: enabledPlugins.length,
      successfully_loaded: this._plugins.size,
    });
  }

  public async loadPlugin(pluginId: string): Promise<void> {
    if (this._plugins.has(pluginId)) {
      return;
    }

    const pluginDir = path.join(this._pluginRootDir, pluginId);
    const manifestPath = path.join(pluginDir, "plugin-manifest.yaml");

    if (!(await fs.pathExists(pluginDir))) {
      throw new PluginException(`插件目录不存在: ${pluginDir}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    if (!(await fs.pathExists(manifestPath))) {
      throw new PluginException(`插件清单不存在: ${manifestPath}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    const manifestRaw = yaml.parse(await fs.readFile(manifestPath, "utf-8"));
    const manifest = this.toManifestLite(manifestRaw, pluginId);

    if (manifest.id !== pluginId) {
      throw new PluginException(`插件ID不匹配: ${pluginId} != ${manifest.id}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    const appVersion = this._hostService.getConfig().app.app_version;
    if (!this.isVersionCompatible(appVersion, manifest.minAppVersion)) {
      throw new PluginException(
        `插件最低版本不兼容: need=${manifest.minAppVersion}, current=${appVersion}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    const entryPath = path.resolve(pluginDir, manifest.main);
    if (!(await fs.pathExists(entryPath))) {
      throw new PluginException(`插件入口不存在: ${entryPath}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const pluginExports = require(entryPath);
    const plugin: SystemPlugin = pluginExports.default;

    if (!plugin || typeof plugin.onActivate !== "function") {
      throw new PluginException(
        `插件入口未通过 'export default' 导出插件实例: ${pluginId}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    const pluginConfig = await this.loadPluginConfig(pluginId, plugin);
    const context = this.createSandboxContext(pluginId, manifest.permissions, pluginConfig);
    this._plugins.set(pluginId, {
      manifest,
      plugin,
      context,
      isRunning: false,
    });

    this._hostService.publishDomainEvent(
      new PluginLoadedEvent(
        {
          pluginId: manifest.id,
          pluginName: manifest.name,
          version: manifest.version,
        },
        createTraceContext()
      )
    );
  }

  public async startPlugin(pluginId: string): Promise<void> {
    const item = this._plugins.get(pluginId);
    if (!item || item.isRunning) {
      return;
    }

    await this.withTimeout(
      Promise.resolve(item.plugin.onActivate(item.context)),
      this._pluginTimeoutMs,
      `插件 ${pluginId} onActivate 超时`
    );

    item.isRunning = true;

    this._hostService.publishDomainEvent(
      new PluginStartedEvent(
        {
          pluginId: item.manifest.id,
          pluginName: item.manifest.name,
          version: item.manifest.version,
        },
        createTraceContext()
      )
    );
  }

  public async startAllPlugins(): Promise<void> {
    for (const pluginId of this._plugins.keys()) {
      if (this._isShuttingDown) break;
      try {
        await this.startPlugin(pluginId);
      } catch (error) {
        this._logger.error("插件启动失败", { plugin_id: pluginId, error: (error as Error).message });
      }
    }
  }

  public async stopPlugin(pluginId: string): Promise<void> {
    const item = this._plugins.get(pluginId);
    if (!item || !item.isRunning) {
      return;
    }

    if (typeof item.plugin.onDeactivate === "function") {
      await this.withTimeout(
        Promise.resolve(item.plugin.onDeactivate()),
        this._pluginTimeoutMs,
        `插件 ${pluginId} onDeactivate 超时`
      );
    }

    for (const sub of item.context.subscriptions) {
      try {
        await Promise.resolve(sub.dispose());
      } catch (error) {
        this._logger.warn("释放插件订阅失败", { plugin_id: pluginId, error: (error as Error).message });
      }
    }
    item.context.subscriptions.length = 0;
    item.isRunning = false;

    this._hostService.publishDomainEvent(
      new PluginStoppedEvent(
        {
          pluginId: item.manifest.id,
          pluginName: item.manifest.name,
          version: item.manifest.version,
        },
        createTraceContext()
      )
    );
  }

  public async stopAllPlugins(): Promise<void> {
    for (const pluginId of Array.from(this._plugins.keys())) {
      if (this._isShuttingDown) break;
      await this.stopPlugin(pluginId);
    }
  }

  public async shutdown(): Promise<void> {
    if (this._isShuttingDown) {
      return;
    }

    this._isShuttingDown = true;
    await this.stopAllPlugins();
    this._plugins.clear();
    this._isInitialized = false;
  }

  private createSandboxContext(
    pluginId: string,
    permissions: Permission[],
    pluginConfig: Record<string, unknown> = {}
  ): ExtensionContext {
    const subscriptions: IDisposable[] = [];
    const storage = this._hostService.createStorage(pluginId);
    const shortTermMemory = this._hostService.createShortTermMemory(pluginId);
    const frozenConfig = this.hasPluginPermission(permissions, Permission.CONFIG_READ_SELF)
      ? Object.freeze({ ...pluginConfig })
      : Object.freeze({});

    return {
      pluginId,
      logger: this._hostService.createLogger(`Plugin:${pluginId}`),
      config: frozenConfig,
      storage: {
        get: (key: string) => storage.get(key),
        set: (key: string, value: unknown) => storage.set(key, value),
        delete: (key: string) => storage.delete(key),
      },
      shortTermMemory: {
        append: async (entry) => {
          this.assertPluginPermission(pluginId, permissions, Permission.MEMORY_SHORT_TERM, "追加短期记忆");
          return shortTermMemory.append(entry);
        },
        getRecent: async (sceneId, limit) => {
          this.assertPluginPermission(pluginId, permissions, Permission.MEMORY_SHORT_TERM, "读取短期记忆");
          return shortTermMemory.getRecent(sceneId, limit);
        },
        getByType: async (sceneId, messageType, limit) => {
          this.assertPluginPermission(pluginId, permissions, Permission.MEMORY_SHORT_TERM, "按类型查询短期记忆");
          return shortTermMemory.getByType(sceneId, messageType, limit);
        },
        clearScene: async (sceneId) => {
          this.assertPluginPermission(pluginId, permissions, Permission.MEMORY_SHORT_TERM, "清空短期记忆");
          return shortTermMemory.clearScene(sceneId);
        },
      },
      subscriptions,
      perception: {
        inject: (event) => {
          this.assertPluginPermission(pluginId, permissions, Permission.PERCEPTION_WRITE, "注入感知事件");
          // Fire-and-forget：inject 立即返回，AI 响应通过 EventBus 异步回传
          void this._hostService.injectPerception(event).catch((err: unknown) => {
            const msg = err instanceof Error ? err.message : String(err);
            this._logger.error(`插件 ${pluginId} 感知注入失败`, { error: msg, trace_id: event.id });
          });
        },
      },
      sceneAttention: {
        reportSceneAttention: (channelId: string, focused: boolean, durationMs?: number) => {
          this._hostService.reportSceneAttention(pluginId, channelId, focused, durationMs);
        },
        isSceneFocused: (channelId: string) => {
          return this._hostService.isSceneFocused(channelId);
        },
        registerSourcePolicies: (policies: Record<string, string>) => {
          this._hostService.registerSourcePolicies(pluginId, policies);
        },
      },
      bus: {
        on: (eventName: string, handler: (payload: unknown) => void) => {
          this.assertPluginPermission(pluginId, permissions, Permission.EVENT_SUBSCRIBE, `订阅事件 ${eventName}`);
          this.assertSubscribableTopic(pluginId, eventName);
          const wrapped = async (evt: unknown) => {
            const payload = (evt as Record<string, unknown>)["payload"] ?? evt;
            await Promise.resolve(handler(payload));
          };
          const disposable = this._hostService.subscribeEvent(eventName, wrapped);
          subscriptions.push(disposable);
          return disposable;
        },
        emit: (eventName: string, payload: unknown) => {
          this.assertPluginPermission(pluginId, permissions, Permission.EVENT_PUBLISH, `发布事件 ${eventName}`);
          this.assertPublishableTopic(pluginId, eventName);
          this._hostService.publishPluginEvent(
            eventName,
            `${pluginId}-${Date.now()}`,
            payload
          );
        },
      },
      agents: {
        registerSubAgent: (profile) => {
          this.assertPluginPermission(pluginId, permissions, Permission.AGENT_REGISTER, `注册子代理 ${profile.name}`);
          const disposable = this._hostService.registerAgent(pluginId, profile);
          subscriptions.push(disposable);
          return disposable;
        },
      },
    };
  }

  private toManifestLite(raw: unknown, pluginId: string): PluginManifestLite {
    const parsed = PluginManifestSchema.safeParse(raw);
    if (!parsed.success) {
      const detail = parsed.error.issues
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ");
      throw new PluginException(`插件清单格式错误: ${pluginId}; ${detail}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    const manifest = parsed.data as PluginManifest;
    if (manifest.id !== pluginId) {
      throw new PluginException(`插件ID不匹配: ${pluginId} != ${manifest.id}`, ErrorCode.PLUGIN_VALIDATION_FAILED);
    }

    return {
      id: manifest.id,
      name: manifest.name,
      version: manifest.version,
      main: manifest.main,
      minAppVersion: manifest.minAppVersion,
      permissions: manifest.permissions,
    };
  }

  private async loadPluginConfig(pluginId: string, plugin: SystemPlugin): Promise<Record<string, unknown>> {
    const pluginConfigPath = path.join(this._hostService.getRepoRoot(), "configs", "plugin", `${pluginId}.yaml`);
    let pluginConfig: Record<string, unknown> = {};

    if (!(await fs.pathExists(pluginConfigPath))) {
      // 插件提供了 configSchema 时，自动生成默认配置文件
      if (plugin.configSchema && typeof plugin.configSchema.safeParse === "function") {
        const { ConfigManager } = await import("../foundation/config/config-manager");
        const generated = await ConfigManager.instance.generatePluginDefaults(pluginId, plugin.configSchema);
        if (generated && await fs.pathExists(pluginConfigPath)) {
          const raw = await fs.readFile(pluginConfigPath, "utf-8");
          pluginConfig = yaml.parse(raw) ?? {};
        }
      }
      if (Object.keys(pluginConfig).length === 0) {
        return pluginConfig;
      }
    }

    try {
      const raw = await fs.readFile(pluginConfigPath, "utf-8");
      pluginConfig = yaml.parse(raw) ?? {};
    } catch (error) {
      throw new PluginException(
        `插件配置文件解析失败: ${pluginId}; ${(error as Error).message}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    if (!plugin.configSchema || typeof plugin.configSchema.safeParse !== "function") {
      return pluginConfig;
    }

    const parsed = plugin.configSchema.safeParse(pluginConfig);
    if (!parsed.success) {
      const issues = parsed.error.issues ?? [];
      const detail = issues
        .map((issue) => `${(issue.path ?? []).join(".")}: ${issue.message}`)
        .join("; ");
      throw new PluginException(
        `插件配置校验失败: ${pluginId}; ${detail || "unknown validation error"}`,
        ErrorCode.PLUGIN_VALIDATION_FAILED
      );
    }

    return parsed.data as Record<string, unknown>;
  }

  private hasPluginPermission(permissions: Permission[], permission: Permission): boolean {
    return hasPermission(permission, permissions);
  }

  private assertPluginPermission(
    pluginId: string,
    permissions: Permission[],
    permission: Permission,
    action: string
  ): void {
    if (this.hasPluginPermission(permissions, permission)) {
      return;
    }
    throw new PluginException(
      `插件 ${pluginId} 缺少权限 ${permission}，无法${action}`,
      ErrorCode.PLUGIN_PERMISSION_DENIED
    );
  }

  private assertSubscribableTopic(pluginId: string, eventName: string): void {
    if (PLUGIN_SUBSCRIBE_TOPICS.has(eventName) || eventName.startsWith(`plugin.${pluginId}.`)) {
      return;
    }
    throw new PluginException(
      `插件 ${pluginId} 不允许订阅事件 ${eventName}`,
      ErrorCode.PLUGIN_PERMISSION_DENIED
    );
  }

  private assertPublishableTopic(pluginId: string, eventName: string): void {
    if (eventName.startsWith(`plugin.${pluginId}.`)) {
      return;
    }
    throw new PluginException(
      `插件 ${pluginId} 仅允许发布 plugin.${pluginId}.* 命名空间事件，当前为 ${eventName}`,
      ErrorCode.PLUGIN_PERMISSION_DENIED
    );
  }

  private async withTimeout<T>(promise: Promise<T>, timeoutMs: number, timeoutMessage: string): Promise<T> {
    let timeoutHandle: NodeJS.Timeout;
    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutHandle = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
    });

    return Promise.race([promise, timeoutPromise]).finally(() => {
      clearTimeout(timeoutHandle);
    });
  }

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
