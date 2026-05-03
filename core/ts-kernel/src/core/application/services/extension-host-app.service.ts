import {
  createTraceContext,
  DomainEvent,
  ExtensionCommandContribution,
  ExtensionCommandHandler,
  ExtensionCommandMetadata,
  IDisposable,
  IExtensionHostService,
  IExtensionLogger,
  IExtensionShortTermMemory,
  IExtensionSystemConfig,
  IKeyValueDB,
  PerceptionEvent,
  SceneAttentionChangedEvent,
  SourceAttentionPolicy,
  SubAgentProfile,
} from '@cradle-selrena/protocol';
import { SubAgentRegistry } from '../../foundation/agent/sub-agent-registry';
import { ConfigManager } from '../../foundation/config/config-manager';
import { EventBus } from '../../foundation/event-bus/event-bus';
import { getLogger } from '../../foundation/logger/logger';
import { ExtensionShortTermMemoryRepository } from '../../foundation/storage/repositories/extension-short-term-memory-repository';
import { ExtensionStorageRepository } from '../../foundation/storage/repositories/extension-storage-repository';
import { resolveRepoRoot } from '../../foundation/utils/path-utils';
import { LifeClockManager } from '../../domain/organism/life-clock/life-clock-manager';
import { PerceptionAppService } from './perception-app.service';

export class ExtensionHostAppService implements IExtensionHostService {
  private readonly _commands = new Map<string, {
    extensionId: string;
    handler: ExtensionCommandHandler;
    metadata?: ExtensionCommandMetadata;
  }>();

  constructor(private readonly _perceptionService: PerceptionAppService) {}

  public getConfig(): IExtensionSystemConfig {
    const config = ConfigManager.instance.getConfig();
    return {
      system: {
        app_version: config.system.app_version,
      },
      extension: {
        extension_root_dir: config.system.extension.extension_root_dir,
        sandbox: {
          timeout_ms: config.system.extension.sandbox.timeout_ms,
        },
      },
    };
  }

  public getRepoRoot(): string {
    return resolveRepoRoot();
  }

  public async loadEnabledExtensions(): Promise<string[]> {
    return ConfigManager.instance.loadEnabledExtensions();
  }

  public createLogger(module: string): IExtensionLogger {
    return getLogger(module);
  }

  public createStorage(extensionId: string): IKeyValueDB {
    return new ExtensionStorageRepository(extensionId);
  }

  public createShortTermMemory(extensionId: string): IExtensionShortTermMemory {
    return new ExtensionShortTermMemoryRepository(extensionId);
  }

  public registerCommand(
    extensionId: string,
    commandId: string,
    handler: ExtensionCommandHandler,
    metadata?: ExtensionCommandMetadata,
  ): IDisposable {
    if (!commandId.startsWith(`${extensionId}.`) && !commandId.startsWith(`${extensionId}:`)) {
      throw new Error(`扩展 ${extensionId} 注册命令必须带命名空间前缀，当前为 ${commandId}`);
    }

    if (this._commands.has(commandId)) {
      throw new Error(`命令已存在: ${commandId}`);
    }

    this._commands.set(commandId, { extensionId, handler, metadata });

    return {
      dispose: () => {
        const current = this._commands.get(commandId);
        if (current?.extensionId === extensionId) {
          this._commands.delete(commandId);
        }
      },
    };
  }

  public async executeCommand(commandId: string, ...args: unknown[]): Promise<unknown> {
    const command = this._commands.get(commandId);
    if (!command) {
      throw new Error(`命令不存在: ${commandId}`);
    }

    return command.handler(...args);
  }

  public async listCommands(): Promise<ExtensionCommandContribution[]> {
    return Array.from(this._commands.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([commandId, entry]) => ({
        command: commandId,
        title: entry.metadata?.title ?? commandId,
        category: entry.metadata?.category,
      }));
  }

  public subscribeEvent(eventName: string, handler: (event: unknown) => Promise<void>): IDisposable {
    const wrappedHandler = async (event: DomainEvent) => {
      await handler(event);
    };

    EventBus.instance.subscribe(eventName, wrappedHandler);
    return {
      dispose: () => EventBus.instance.unsubscribe(eventName, wrappedHandler),
    };
  }

  public publishExtensionEvent(eventType: string, eventId: string, payload: unknown): void {
    void EventBus.instance.publish({
      event_type: eventType,
      event_id: eventId,
      trace_context: createTraceContext(),
      payload,
    } as never);
  }

  public publishDomainEvent(event: DomainEvent): void {
    void EventBus.instance.publish(event);
  }

  public async injectPerception(event: PerceptionEvent): Promise<void> {
    await this._perceptionService.processIngress(event);
  }

  public reportSceneAttention(
    extensionId: string,
    channelId: string,
    focused: boolean,
    durationMs?: number,
  ): void {
    void EventBus.instance.publish(
      new SceneAttentionChangedEvent(
        {
          channelId,
          focused,
          extensionId,
          durationMs,
        },
        createTraceContext(),
      ),
    );
  }

  public isSceneFocused(channelId: string): boolean {
    return LifeClockManager.instance.getChannelFocused(channelId);
  }

  public registerSourcePolicies(_extensionId: string, policies: Record<string, string>): void {
    LifeClockManager.instance.registerSourcePolicies(policies as Record<string, SourceAttentionPolicy>);
  }

  public registerAgent(extensionId: string, profile: SubAgentProfile): IDisposable {
    SubAgentRegistry.instance.register(extensionId, profile);
    return {
      dispose: () => SubAgentRegistry.instance.unregister(extensionId, profile.name),
    };
  }
}