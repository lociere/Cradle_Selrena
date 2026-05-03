import fs from 'fs-extra';
import path from 'path';
import yaml from 'yaml';
import {
  createTraceContext,
  ErrorCode,
  ExtensionCommandMetadata,
  ExtensionContext,
  ExtensionErrorEvent,
  ExtensionException,
  ExtensionLoadedEvent,
  ExtensionManifest,
  ExtensionManifestSchema,
  ExtensionStartedEvent,
  ExtensionStoppedEvent,
  ExtensionSystemEventTopics,
  hasPermission,
  IExtensionHostService,
  IExtensionLogger,
  IDisposable,
  Permission,
  SystemExtension,
} from '@cradle-selrena/protocol';

type ExtensionManifestLite = {
  id: string;
  name: string;
  version: string;
  main: string;
  minAppVersion: string;
  permissions: Permission[];
  extensionKind: ExtensionManifest['extensionKind'];
  activationEvents: ExtensionManifest['activationEvents'];
  contributes: ExtensionManifest['contributes'];
};

type ExtensionModuleExport =
  | SystemExtension
  | {
      extension: SystemExtension;
      manifest?: Partial<ExtensionManifest>;
    };

interface ExtensionInstance {
  manifest: ExtensionManifestLite;
  extension: SystemExtension;
  context: ExtensionContext;
  isRunning: boolean;
}

const EXTENSION_SUBSCRIBE_TOPICS = new Set<string>(Object.values(ExtensionSystemEventTopics));

export class ExtensionManager {
  private _extensionRootDir: string = path.resolve(process.cwd(), 'extensions');
  private _extensions = new Map<string, ExtensionInstance>();
  private _extensionDirectoryIndex = new Map<string, string>();
  private _extensionTimeoutMs = 5000;
  private _isInitialized = false;
  private _isShuttingDown = false;
  private readonly _logger: IExtensionLogger;

  constructor(private readonly _hostService: IExtensionHostService) {
    this._logger = _hostService.createLogger('extension-manager');
  }

  public async init(): Promise<void> {
    if (this._isInitialized) {
      this._logger.warn('扩展管理器已初始化，跳过重复初始化');
      return;
    }

    const config = this._hostService.getConfig();
    this._extensionRootDir = path.resolve(
      this._hostService.getRepoRoot(),
      config.extension.extension_root_dir,
    );
    this._extensionTimeoutMs = config.extension.sandbox.timeout_ms;

    await fs.ensureDir(this._extensionRootDir);
    this._extensionDirectoryIndex = await this.discoverExtensionDirectories();

    const enabledExtensions = await this._hostService.loadEnabledExtensions();
    this._logger.info('读取启用扩展列表', { enabled_extensions: enabledExtensions });

    for (const extensionId of enabledExtensions) {
      if (this._isShuttingDown) {
        break;
      }

      try {
        await this.loadExtension(extensionId);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        this._logger.error('扩展加载失败，已跳过', { extension_id: extensionId, error: message });
        this._hostService.publishDomainEvent(
          new ExtensionErrorEvent(
            {
              extensionId,
              error: message,
              stack: error instanceof Error ? error.stack : undefined,
            },
            createTraceContext(),
          ),
        );
      }
    }

    this._isInitialized = true;
    this._logger.info('扩展管理器初始化完成', {
      total_enabled: enabledExtensions.length,
      successfully_loaded: this._extensions.size,
    });
  }

  public async loadExtension(extensionId: string): Promise<void> {
    if (this._extensions.has(extensionId)) {
      return;
    }

    const extensionDir = await this.resolveExtensionDirectory(extensionId);
    const manifestPath = path.join(extensionDir, 'extension-manifest.yaml');

    if (!(await fs.pathExists(extensionDir))) {
      throw new ExtensionException(
        `扩展目录不存在: ${extensionDir}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    if (!(await fs.pathExists(manifestPath))) {
      throw new ExtensionException(
        `扩展清单不存在: ${manifestPath}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    const manifestRaw = yaml.parse(await fs.readFile(manifestPath, 'utf-8'));
    const manifestFromYaml = this.toManifestLite(manifestRaw, extensionId);

    if (manifestFromYaml.id !== extensionId) {
      throw new ExtensionException(
        `扩展 ID 不匹配: ${extensionId} != ${manifestFromYaml.id}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    const appVersion = this._hostService.getConfig().system.app_version;
    if (!this.isVersionCompatible(appVersion, manifestFromYaml.minAppVersion)) {
      throw new ExtensionException(
        `扩展最低版本不兼容: need=${manifestFromYaml.minAppVersion}, current=${appVersion}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    const entryPath = path.resolve(extensionDir, manifestFromYaml.main);
    if (!(await fs.pathExists(entryPath))) {
      throw new ExtensionException(
        `扩展入口不存在: ${entryPath}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const requiredModule = require(entryPath);
    const exportedValue = requiredModule.default ?? requiredModule;
    const resolvedExport = this.resolveExtensionExport(exportedValue);
    const manifest = this.toManifestLite(
      resolvedExport.manifest ? { ...manifestRaw, ...resolvedExport.manifest } : manifestRaw,
      extensionId,
    );

    if (!resolvedExport.extension || typeof resolvedExport.extension.onActivate !== 'function') {
      throw new ExtensionException(
        `扩展入口没有导出合法的扩展实例: ${extensionId}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    const extensionConfig = await this.loadExtensionConfig(extensionId, resolvedExport.extension);
    const context = this.createSandboxContext(extensionId, manifest.permissions, extensionConfig);

    this._extensions.set(extensionId, {
      manifest,
      extension: resolvedExport.extension,
      context,
      isRunning: false,
    });

    this._hostService.publishDomainEvent(
      new ExtensionLoadedEvent(
        {
          extensionId: manifest.id,
          name: manifest.name,
          version: manifest.version,
        },
        createTraceContext(),
      ),
    );
  }

  public async startExtension(extensionId: string): Promise<void> {
    const item = this._extensions.get(extensionId);
    if (!item || item.isRunning) {
      return;
    }

    await this.withTimeout(
      Promise.resolve(item.extension.onActivate(item.context)),
      this._extensionTimeoutMs,
      `扩展 ${extensionId} onActivate 超时`,
    );

    item.isRunning = true;
    this._hostService.publishDomainEvent(
      new ExtensionStartedEvent(
        {
          extensionId: item.manifest.id,
          name: item.manifest.name,
          version: item.manifest.version,
        },
        createTraceContext(),
      ),
    );
  }

  public async startAllExtensions(): Promise<void> {
    for (const extensionId of this._extensions.keys()) {
      if (this._isShuttingDown) {
        break;
      }

      try {
        await this.startExtension(extensionId);
      } catch (error) {
        this._logger.error('扩展启动失败', {
          extension_id: extensionId,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
  }

  public async stopExtension(extensionId: string): Promise<void> {
    const item = this._extensions.get(extensionId);
    if (!item || !item.isRunning) {
      return;
    }

    if (typeof item.extension.onDeactivate === 'function') {
      await this.withTimeout(
        Promise.resolve(item.extension.onDeactivate()),
        this._extensionTimeoutMs,
        `扩展 ${extensionId} onDeactivate 超时`,
      );
    }

    for (const subscription of item.context.subscriptions) {
      try {
        await Promise.resolve(subscription.dispose());
      } catch (error) {
        this._logger.warn('释放扩展订阅失败', {
          extension_id: extensionId,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    item.context.subscriptions.length = 0;
    item.isRunning = false;

    this._hostService.publishDomainEvent(
      new ExtensionStoppedEvent(
        {
          extensionId: item.manifest.id,
          name: item.manifest.name,
          version: item.manifest.version,
        },
        createTraceContext(),
      ),
    );
  }

  public async stopAllExtensions(): Promise<void> {
    for (const extensionId of Array.from(this._extensions.keys())) {
      if (this._isShuttingDown) {
        break;
      }
      await this.stopExtension(extensionId);
    }
  }

  public async shutdown(): Promise<void> {
    if (this._isShuttingDown) {
      return;
    }

    this._isShuttingDown = true;
    await this.stopAllExtensions();
    this._extensions.clear();
    this._extensionDirectoryIndex.clear();
    this._isInitialized = false;
  }

  private async resolveExtensionDirectory(extensionId: string): Promise<string> {
    if (!this._extensionDirectoryIndex.size) {
      this._extensionDirectoryIndex = await this.discoverExtensionDirectories();
    }

    const extensionDir = this._extensionDirectoryIndex.get(extensionId);
    if (!extensionDir) {
      throw new ExtensionException(
        `未找到扩展目录: ${extensionId}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    return extensionDir;
  }

  private async discoverExtensionDirectories(): Promise<Map<string, string>> {
    const index = new Map<string, string>();
    await this.walkExtensionTree(this._extensionRootDir, index);
    return index;
  }

  private async walkExtensionTree(currentDir: string, index: Map<string, string>): Promise<void> {
    const entries = await fs.readdir(currentDir, { withFileTypes: true });
    const hasManifest = entries.some((entry) => entry.isFile() && entry.name === 'extension-manifest.yaml');

    if (hasManifest) {
      try {
        const manifestPath = path.join(currentDir, 'extension-manifest.yaml');
        const manifestRaw = yaml.parse(await fs.readFile(manifestPath, 'utf-8')) as { id?: unknown };
        const extensionId = typeof manifestRaw?.id === 'string' ? manifestRaw.id.trim() : '';

        if (!extensionId) {
          this._logger.warn('扩展清单缺少 id，已跳过索引', { extension_dir: currentDir });
          return;
        }

        if (index.has(extensionId)) {
          this._logger.warn('检测到重复扩展 ID，后续目录将被忽略', {
            extension_id: extensionId,
            existing_dir: index.get(extensionId),
            duplicate_dir: currentDir,
          });
          return;
        }

        index.set(extensionId, currentDir);
      } catch (error) {
        this._logger.warn('扩展索引建立失败，已跳过目录', {
          extension_dir: currentDir,
          error: error instanceof Error ? error.message : String(error),
        });
      }

      return;
    }

    for (const entry of entries) {
      if (!entry.isDirectory() || this.shouldSkipExtensionDirectory(entry.name)) {
        continue;
      }
      await this.walkExtensionTree(path.join(currentDir, entry.name), index);
    }
  }

  private shouldSkipExtensionDirectory(dirName: string): boolean {
    return dirName === 'node_modules' || dirName === 'dist' || dirName === 'build' || dirName.startsWith('.');
  }

  private createSandboxContext(
    extensionId: string,
    permissions: Permission[],
    extensionConfig: Record<string, unknown> = {},
  ): ExtensionContext {
    const subscriptions: IDisposable[] = [];
    const storage = this._hostService.createStorage(extensionId);
    const shortTermMemory = this._hostService.createShortTermMemory(extensionId);
    const frozenConfig = this.hasExtensionPermission(permissions, Permission.CONFIG_READ_SELF)
      ? Object.freeze({ ...extensionConfig })
      : Object.freeze({});

    return {
      extensionId,
      logger: this._hostService.createLogger(`Extension:${extensionId}`),
      config: frozenConfig,
      storage: {
        get: (key: string) => storage.get(key),
        set: (key: string, value: unknown) => storage.set(key, value),
        delete: (key: string) => storage.delete(key),
      },
      shortTermMemory: {
        append: async (entry) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.MEMORY_SHORT_TERM, '追加短期记忆');
          return shortTermMemory.append(entry);
        },
        getRecent: async (sceneId, limit) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.MEMORY_SHORT_TERM, '读取短期记忆');
          return shortTermMemory.getRecent(sceneId, limit);
        },
        getByType: async (sceneId, messageType, limit) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.MEMORY_SHORT_TERM, '按类型查询短期记忆');
          return shortTermMemory.getByType(sceneId, messageType, limit);
        },
        clearScene: async (sceneId) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.MEMORY_SHORT_TERM, '清空短期记忆');
          return shortTermMemory.clearScene(sceneId);
        },
      },
      subscriptions,
      perception: {
        inject: (event) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.PERCEPTION_WRITE, '注入感知事件');
          void this._hostService.injectPerception(event).catch((error: unknown) => {
            this._logger.error(`扩展 ${extensionId} 感知注入失败`, {
              error: error instanceof Error ? error.message : String(error),
              trace_id: event.id,
            });
          });
        },
      },
      sceneAttention: {
        reportSceneAttention: (channelId: string, focused: boolean, durationMs?: number) => {
          this._hostService.reportSceneAttention(extensionId, channelId, focused, durationMs);
        },
        isSceneFocused: (channelId: string) => this._hostService.isSceneFocused(channelId),
        registerSourcePolicies: (policies: Record<string, string>) => {
          this._hostService.registerSourcePolicies(extensionId, policies);
        },
      },
      bus: {
        on: (eventName: string, handler: (payload: unknown) => void) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.EVENT_SUBSCRIBE, `订阅事件 ${eventName}`);
          this.assertSubscribableTopic(extensionId, eventName);

          const wrappedHandler = async (event: unknown) => {
            const payload = (event as Record<string, unknown>)['payload'] ?? event;
            await Promise.resolve(handler(payload));
          };

          const disposable = this._hostService.subscribeEvent(eventName, wrappedHandler);
          subscriptions.push(disposable);
          return disposable;
        },
        emit: (eventName: string, payload: unknown) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.EVENT_PUBLISH, `发布事件 ${eventName}`);
          this.assertPublishableTopic(extensionId, eventName);
          this._hostService.publishExtensionEvent(eventName, `${extensionId}-${Date.now()}`, payload);
        },
      },
      agents: {
        registerSubAgent: (profile) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.AGENT_REGISTER, `注册子代理 ${profile.name}`);
          const disposable = this._hostService.registerAgent(extensionId, profile);
          subscriptions.push(disposable);
          return disposable;
        },
      },
      commands: {
        registerCommand: (commandId: string, handler, metadata?: ExtensionCommandMetadata) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.COMMAND_REGISTER, `注册命令 ${commandId}`);
          const disposable = this._hostService.registerCommand(extensionId, commandId, handler, metadata);
          subscriptions.push(disposable);
          return disposable;
        },
        executeCommand: async (commandId: string, ...args: unknown[]) => {
          this.assertExtensionPermission(extensionId, permissions, Permission.COMMAND_EXECUTE, `执行命令 ${commandId}`);
          return this._hostService.executeCommand(commandId, ...args);
        },
        listCommands: async () => this._hostService.listCommands(),
      },
    };
  }

  private resolveExtensionExport(exportedValue: ExtensionModuleExport): {
    extension: SystemExtension;
    manifest?: Partial<ExtensionManifest>;
  } {
    if (
      exportedValue &&
      typeof exportedValue === 'object' &&
      'extension' in exportedValue &&
      exportedValue.extension &&
      typeof exportedValue.extension === 'object'
    ) {
      return {
        extension: exportedValue.extension,
        manifest: exportedValue.manifest,
      };
    }

    return {
      extension: exportedValue as SystemExtension,
    };
  }

  private toManifestLite(raw: unknown, extensionId: string): ExtensionManifestLite {
    const parsed = ExtensionManifestSchema.safeParse(raw);
    if (!parsed.success) {
      const detail = parsed.error.issues
        .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
        .join('; ');
      throw new ExtensionException(
        `扩展清单格式错误: ${extensionId}; ${detail}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    const manifest = parsed.data as ExtensionManifest;
    if (manifest.id !== extensionId) {
      throw new ExtensionException(
        `扩展 ID 不匹配: ${extensionId} != ${manifest.id}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    return {
      id: manifest.id,
      name: manifest.name,
      version: manifest.version,
      main: manifest.main,
      minAppVersion: manifest.minAppVersion,
      permissions: manifest.permissions,
      extensionKind: manifest.extensionKind,
      activationEvents: manifest.activationEvents,
      contributes: manifest.contributes,
    };
  }

  private async loadExtensionConfig(
    extensionId: string,
    extension: SystemExtension,
  ): Promise<Record<string, unknown>> {
    const extensionConfigPath = path.join(
      this._hostService.getRepoRoot(),
      'configs',
      'extension',
      `${extensionId}.yaml`,
    );

    let extensionConfig: Record<string, unknown> = {};

    if (!(await fs.pathExists(extensionConfigPath))) {
      if (extension.configSchema && typeof extension.configSchema.safeParse === 'function') {
        const { ConfigManager } = await import('../foundation/config/config-manager.js');
        const generated = await ConfigManager.instance.generateExtensionDefaults(
          extensionId,
          extension.configSchema,
        );
        if (generated && (await fs.pathExists(extensionConfigPath))) {
          const raw = await fs.readFile(extensionConfigPath, 'utf-8');
          extensionConfig = yaml.parse(raw) ?? {};
        }
      }

      if (Object.keys(extensionConfig).length === 0) {
        return extensionConfig;
      }
    }

    try {
      const raw = await fs.readFile(extensionConfigPath, 'utf-8');
      extensionConfig = yaml.parse(raw) ?? {};
    } catch (error) {
      throw new ExtensionException(
        `扩展配置解析失败: ${extensionId}; ${error instanceof Error ? error.message : String(error)}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    if (!extension.configSchema || typeof extension.configSchema.safeParse !== 'function') {
      return extensionConfig;
    }

    const parsed = extension.configSchema.safeParse(extensionConfig);
    if (!parsed.success) {
      const detail = (parsed.error.issues ?? [])
        .map((issue) => `${(issue.path ?? []).join('.')}: ${issue.message}`)
        .join('; ');
      throw new ExtensionException(
        `扩展配置校验失败: ${extensionId}; ${detail || 'unknown validation error'}`,
        ErrorCode.EXTENSION_VALIDATION_FAILED,
      );
    }

    return parsed.data as Record<string, unknown>;
  }

  private hasExtensionPermission(permissions: Permission[], permission: Permission): boolean {
    return hasPermission(permission, permissions);
  }

  private assertExtensionPermission(
    extensionId: string,
    permissions: Permission[],
    permission: Permission,
    action: string,
  ): void {
    if (this.hasExtensionPermission(permissions, permission)) {
      return;
    }

    throw new ExtensionException(
      `扩展 ${extensionId} 缺少权限 ${permission}，无法${action}`,
      ErrorCode.EXTENSION_PERMISSION_DENIED,
    );
  }

  private assertSubscribableTopic(extensionId: string, eventName: string): void {
    if (EXTENSION_SUBSCRIBE_TOPICS.has(eventName) || eventName.startsWith(`extension.${extensionId}.`)) {
      return;
    }

    throw new ExtensionException(
      `扩展 ${extensionId} 不允许订阅事件 ${eventName}`,
      ErrorCode.EXTENSION_PERMISSION_DENIED,
    );
  }

  private assertPublishableTopic(extensionId: string, eventName: string): void {
    if (eventName.startsWith(`extension.${extensionId}.`)) {
      return;
    }

    throw new ExtensionException(
      `扩展 ${extensionId} 仅允许发布 extension.${extensionId}.* 命名空间事件，当前为 ${eventName}`,
      ErrorCode.EXTENSION_PERMISSION_DENIED,
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
    const parseVersion = (value: string): number[] => value.split('.').map((item) => Number.parseInt(item, 10));
    const currentParts = parseVersion(current);
    const requiredParts = parseVersion(minRequired);

    for (let index = 0; index < Math.max(currentParts.length, requiredParts.length); index += 1) {
      const currentValue = currentParts[index] ?? 0;
      const requiredValue = requiredParts[index] ?? 0;
      if (currentValue > requiredValue) {
        return true;
      }
      if (currentValue < requiredValue) {
        return false;
      }
    }

    return true;
  }
}