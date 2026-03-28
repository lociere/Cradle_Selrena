/**
 * IPluginHostService — 插件宿主服务端口
 *
 * 这是 Host 层（插件加载器）与 Application/Infrastructure 层之间的
 * 唯一依赖入口点，是 Soul-Vessel 架构的绝对隔离边界。
 *
 * PluginManager 只允许通过此接口获取全部能力，
 * 不得直接导入 foundation/ 或 application/ 的任何具体类。
 */
import { DomainEvent } from '../events/domain-events';
import {
  IDisposable,
  IKeyValueDB,
  IPluginLogger,
  IPluginShortTermMemory,
  PerceptionEvent,
  SubAgentProfile,
} from '../plugin/sdk';

/**
 * 插件管理器所需的最小配置视图。
 * Vessel/Application 层将 GlobalConfig 投影为此精简接口后传入。
 */
export interface IPluginSystemConfig {
  app: {
    app_version: string;
  };
  plugin: {
    plugin_root_dir: string;
    sandbox: {
      timeout_ms: number;
    };
  };
}

/**
 * 插件宿主服务接口
 * PluginManager 通过构造函数注入，依赖此接口而非具体实现。
 */
export interface IPluginHostService {
  // ── 配置与路径 ──────────────────────────────────────────
  /** 获取插件系统所需的最小配置视图 */
  getConfig(): IPluginSystemConfig;
  /** 获取仓库根目录绝对路径 */
  getRepoRoot(): string;
  /** 读取已启用的插件 ID 列表 */
  loadEnabledPlugins(): Promise<string[]>;

  // ── 插件资源工厂 ─────────────────────────────────────────
  /** 创建模块日志器 */
  createLogger(module: string): IPluginLogger;
  /** 创建指定插件的 K/V 存储实例 */
  createStorage(pluginId: string): IKeyValueDB;
  /** 创建指定插件的短期记忆实例 */
  createShortTermMemory(pluginId: string): IPluginShortTermMemory;

  // ── 事件总线 ──────────────────────────────────────────────
  /**
   * 订阅指定事件，返回可用于取消订阅的 IDisposable。
   * handler 为异步函数，接收原始事件对象。
   */
  subscribeEvent(
    eventName: string,
    handler: (event: unknown) => Promise<void>
  ): IDisposable;
  /**
   * 发布简单插件事件（event_type + payload 封装）。
   * 用于插件通过 ctx.bus.emit 触发的事件。
   */
  publishPluginEvent(eventType: string, eventId: string, payload: unknown): void;
  /**
   * 发布完整领域事件（如 PluginLoadedEvent）。
   * 用于插件管理器发布自身生命周期事件。
   */
  publishDomainEvent(event: DomainEvent): void;

  // ── 感知注入 ──────────────────────────────────────────────
  /** 将感知事件注入感知处理管线 */
  injectPerception(event: PerceptionEvent): Promise<void>;

  // ── 场景注意力 ────────────────────────────────────────────
  /** 上报频道聚焦状态变更（触发 SceneAttentionChangedEvent） */
  reportSceneAttention(
    pluginId: string,
    channelId: string,
    focused: boolean,
    durationMs?: number
  ): void;
  /** 查询指定频道当前是否处于焦点状态 */
  isSceneFocused(channelId: string): boolean;
  /** 注册来源类型的注意力策略（由插件在激活时注入） */
  registerSourcePolicies(pluginId: string, policies: Record<string, string>): void;

  // ── 子代理注册 ────────────────────────────────────────────
  /** 注册子代理，返回用于注销的 IDisposable */
  registerAgent(pluginId: string, profile: SubAgentProfile): IDisposable;
}
