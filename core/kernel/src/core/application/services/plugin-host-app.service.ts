/**
 * PluginHostAppService
 * IPluginHostService 的标准实现，是 Host 层与 Application/Foundation 层之间的唯一桥梁。
 *
 * 职责：
 * - 将 Foundation 层能力（ConfigManager, EventBus, DBManager 等）统一暴露给 PluginManager
 * - 将感知注入请求转发至 PerceptionAppService
 * - 将场景注意力变更转化为 SceneAttentionChangedEvent 发布到事件总线
 * - 提供子代理注册的标准化入口
 */
import {
  IPluginHostService,
  IPluginSystemConfig,
  IDisposable,
  IKeyValueDB,
  IPluginLogger,
  IPluginShortTermMemory,
  DomainEvent,
  PerceptionEvent,
  SubAgentProfile,
  SceneAttentionChangedEvent,
  createTraceContext,
} from '@cradle-selrena/protocol';
import { getLogger } from '../../foundation/logger/logger';
import { ConfigManager } from '../../foundation/config/config-manager';
import { EventBus } from '../../foundation/event-bus/event-bus';
import { resolveRepoRoot } from '../../foundation/utils/path-utils';
import { PluginStorageRepository } from '../../foundation/storage/repositories/plugin-storage-repository';
import { PluginShortTermMemoryRepository } from '../../foundation/storage/repositories/plugin-short-term-memory-repository';
import { SubAgentRegistry } from '../../foundation/agent/sub-agent-registry';
import { PerceptionAppService } from './perception-app.service';
import { LifeClockManager } from '../../domain/organism/life-clock/life-clock-manager';

export class PluginHostAppService implements IPluginHostService {
  constructor(private readonly _perceptionService: PerceptionAppService) {}

  // ── 配置与路径 ────────────────────────────────────────────

  getConfig(): IPluginSystemConfig {
    const cfg = ConfigManager.instance.getConfig();
    return {
      app: { app_version: cfg.app.app_version },
      plugin: {
        plugin_root_dir: cfg.kernel.plugin.plugin_root_dir,
        sandbox: { timeout_ms: cfg.kernel.plugin.sandbox.timeout_ms },
      },
    };
  }

  getRepoRoot(): string {
    return resolveRepoRoot();
  }

  async loadEnabledPlugins(): Promise<string[]> {
    return ConfigManager.instance.loadEnabledPlugins();
  }

  // ── 插件资源工厂 ──────────────────────────────────────────

  createLogger(module: string): IPluginLogger {
    return getLogger(module);
  }

  createStorage(pluginId: string): IKeyValueDB {
    return new PluginStorageRepository(pluginId);
  }

  createShortTermMemory(pluginId: string): IPluginShortTermMemory {
    return new PluginShortTermMemoryRepository(pluginId);
  }

  // ── 事件总线 ──────────────────────────────────────────────

  subscribeEvent(
    eventName: string,
    handler: (event: unknown) => Promise<void>
  ): IDisposable {
    const bus = EventBus.instance;
    const wrappedHandler = async (event: DomainEvent) => {
      await handler(event);
    };
    bus.subscribe(eventName, wrappedHandler);
    return {
      dispose: () => bus.unsubscribe(eventName, wrappedHandler),
    };
  }

  publishPluginEvent(eventType: string, eventId: string, payload: unknown): void {
    EventBus.instance.publish({
      event_type: eventType,
      event_id: eventId,
      trace_context: createTraceContext(),
      payload,
    } as any);
  }

  publishDomainEvent(event: DomainEvent): void {
    EventBus.instance.publish(event);
  }

  // ── 感知注入 ──────────────────────────────────────────────

  async injectPerception(event: PerceptionEvent): Promise<void> {
    await this._perceptionService.processIngress(event);
  }

  // ── 场景注意力 ────────────────────────────────────────────

  reportSceneAttention(pluginId: string, channelId: string, focused: boolean, durationMs?: number): void {
    EventBus.instance.publish(
      new SceneAttentionChangedEvent(
        { channelId, focused, pluginId, durationMs },
        createTraceContext()
      )
    );
  }

  isSceneFocused(channelId: string): boolean {
    return LifeClockManager.instance.getChannelFocused(channelId);
  }

  registerSourcePolicies(_pluginId: string, policies: Record<string, string>): void {
    LifeClockManager.instance.registerSourcePolicies(
      policies as Record<string, import('@cradle-selrena/protocol').SourceAttentionPolicy>,
    );
  }

  // ── 子代理注册 ────────────────────────────────────────────

  registerAgent(pluginId: string, profile: SubAgentProfile): IDisposable {
    SubAgentRegistry.instance.register(pluginId, profile);
    return {
      dispose: () => SubAgentRegistry.instance.unregister(pluginId, profile.name),
    };
  }
}
