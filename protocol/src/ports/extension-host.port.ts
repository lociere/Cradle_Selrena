import { DomainEvent } from '../events/domain-events';
import {
  IDisposable,
  ExtensionCommandContribution,
  ExtensionCommandHandler,
  ExtensionCommandMetadata,
  IKeyValueDB,
  IExtensionLogger,
  IExtensionShortTermMemory,
  PerceptionEvent,
  SubAgentProfile,
} from '../extension/sdk';

export interface IExtensionSystemConfig {
  system: {
    app_version: string;
  };
  extension: {
    extension_root_dir: string;
    sandbox: {
      timeout_ms: number;
    };
  };
}

export interface IExtensionHostService {
  getConfig(): IExtensionSystemConfig;
  getRepoRoot(): string;
  loadEnabledExtensions(): Promise<string[]>;

  createLogger(module: string): IExtensionLogger;
  createStorage(extensionId: string): IKeyValueDB;
  createShortTermMemory(extensionId: string): IExtensionShortTermMemory;
  registerCommand(
    extensionId: string,
    commandId: string,
    handler: ExtensionCommandHandler,
    metadata?: ExtensionCommandMetadata,
  ): IDisposable;
  executeCommand(commandId: string, ...args: unknown[]): Promise<unknown>;
  listCommands(): Promise<ExtensionCommandContribution[]>;

  subscribeEvent(eventName: string, handler: (event: unknown) => Promise<void>): IDisposable;
  publishExtensionEvent(eventType: string, eventId: string, payload: unknown): void;
  publishDomainEvent(event: DomainEvent): void;

  injectPerception(event: PerceptionEvent): Promise<void>;

  reportSceneAttention(
    extensionId: string,
    channelId: string,
    focused: boolean,
    durationMs?: number,
  ): void;
  isSceneFocused(channelId: string): boolean;
  registerSourcePolicies(extensionId: string, policies: Record<string, string>): void;

  registerAgent(extensionId: string, profile: SubAgentProfile): IDisposable;
}

