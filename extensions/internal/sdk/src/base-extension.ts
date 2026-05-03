/**
 * Extension SDK - BaseExtension
 *
 * Abstract base class for all Cradle Selrena extensions.
 * Encapsulates lifecycle management, subscription tracking, and context accessors,
 * mirroring the VS Code / Obsidian extension pattern.
 *
 * Usage:
 *   import { BaseExtension } from '@cradle-selrena/extension-sdk';
 *   import { MyConfigSchema } from './config/schema';
 *   import type { z } from 'zod';
 *
 *   type Config = z.infer<typeof MyConfigSchema>;
 *
 *   export class MyExtension extends BaseExtension<Config> {
 *     constructor() { super(MyConfigSchema); }
 *     protected async activate(): Promise<void> { ... }
 *     protected async deactivate(): Promise<void> { ... }
 *   }
 *
 *   export default new MyExtension();
 */

import type {
  ExtensionContext,
  ExtensionCommandContribution,
  ExtensionCommandMetadata,
  IDisposable,
  IExtensionLogger,
  ExtensionEventPayloadMap,
  SystemExtension,
} from '@cradle-selrena/protocol';
import type { ZodTypeAny } from 'zod';

export abstract class BaseExtension<TConfig = unknown> implements SystemExtension<TConfig> {
  /** Zod schema used by ExtensionManager to validate config before activation. */
  readonly configSchema: ZodTypeAny | undefined;

  private _ctx: ExtensionContext<TConfig> | null = null;

  constructor(configSchema?: ZodTypeAny) {
    this.configSchema = configSchema;
  }

  // 鈹€鈹€ Context accessors (available after activate()) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  /** Extension-scoped logger. Throws if accessed before activation. */
  protected get logger(): IExtensionLogger {
    if (!this._ctx) throw new Error(`${this.constructor.name}: context not initialized`);
    return this._ctx.logger;
  }

  /** Validated, type-safe config object. Throws if accessed before activation. */
  protected get config(): TConfig {
    if (!this._ctx) throw new Error(`${this.constructor.name}: context not initialized`);
    return this._ctx.config;
  }

  /** Full sandbox context. Throws if accessed before activation. */
  protected get ctx(): ExtensionContext<TConfig> {
    if (!this._ctx) throw new Error(`${this.constructor.name}: context not initialized`);
    return this._ctx;
  }

  // 鈹€鈹€ Resource management 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  /**
   * Subscribe to a typed event topic.
   * The subscription is automatically registered in `ctx.subscriptions`
   * and cleaned up by ExtensionManager on deactivation.
   *
   * Known topics (from ExtensionEventPayloadMap) provide full type inference;
   * custom topics fall back to `unknown`.
   */
  protected subscribe<K extends keyof ExtensionEventPayloadMap>(
    eventName: K,
    handler: (payload: ExtensionEventPayloadMap[K]) => void,
  ): IDisposable;
  protected subscribe(eventName: string, handler: (payload: unknown) => void): IDisposable;
  protected subscribe(eventName: string, handler: (payload: unknown) => void): IDisposable {
    const d = this.ctx.bus.on(eventName, handler);
    this.ctx.subscriptions.push(d);
    return d;
  }

  /**
   * Register any disposable resource for automatic cleanup on deactivation.
   * e.g. external connections, file watchers, custom timers.
   */
  protected addDisposable(d: IDisposable): IDisposable {
    this.ctx.subscriptions.push(d);
    return d;
  }

  /**
   * Register a recurring timer that is automatically cleared on deactivation.
  * Exceptions thrown in the callback are caught and logged; they never
  * propagate and interrupt the extension.
   */
  protected registerInterval(
    callback: () => void | Promise<void>,
    intervalMs: number,
  ): IDisposable {
    const id = setInterval(() => {
      Promise.resolve(callback()).catch((err) => {
        this.logger.error(
          '[interval] uncaught error: ' + (err instanceof Error ? err.message : String(err)),
        );
      });
    }, intervalMs);
    return this.addDisposable({ dispose: () => clearInterval(id) });
  }

  /**
  * Register a one-shot timer that is automatically cancelled if the extension
   * is deactivated before it fires.
   */
  protected registerTimeout(
    callback: () => void | Promise<void>,
    delayMs: number,
  ): IDisposable {
    const id = setTimeout(() => {
      Promise.resolve(callback()).catch((err) => {
        this.logger.error(
          '[timeout] uncaught error: ' + (err instanceof Error ? err.message : String(err)),
        );
      });
    }, delayMs);
    return this.addDisposable({ dispose: () => clearTimeout(id) });
  }

  /**
   * Register a command in VS Code-style shape.
    * Command IDs must be namespaced by extensionId, e.g. `napcat-adapter.refresh`.
   */
  protected registerCommand(
    commandId: string,
    handler: (...args: unknown[]) => Promise<unknown> | unknown,
    metadata?: ExtensionCommandMetadata,
  ): IDisposable {
    const disposable = this.ctx.commands.registerCommand(commandId, handler, metadata);
    this.ctx.subscriptions.push(disposable);
    return disposable;
  }

  /** Execute another registered extension command. */
  protected async executeCommand(commandId: string, ...args: unknown[]): Promise<unknown> {
    return this.ctx.commands.executeCommand(commandId, ...args);
  }

  /** List all registered extension commands and their display metadata. */
  protected async listCommands(): Promise<ExtensionCommandContribution[]> {
    return this.ctx.commands.listCommands();
  }

  // 鈹€鈹€ SystemExtension contract (called by ExtensionManager) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  async onActivate(ctx: ExtensionContext<TConfig>): Promise<void> {
    this._ctx = ctx;
    await this.activate();
  }

  async onDeactivate(): Promise<void> {
    try {
      await this.deactivate();
    } finally {
      this._ctx = null;
    }
  }

  // 鈹€鈹€ Subclass extension points 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

  /** [required] Extension initialization: start services, subscribe to events, etc. */
  protected abstract activate(): Promise<void> | void;

  /**
  * [optional] Extension cleanup: release resources not tracked by subscriptions.
   * Subclasses of `WsAdapterExtension` MUST call `await super.deactivate()`.
   * `ctx.subscriptions` cleanup is ExtensionManager's responsibility.
   */
  protected async deactivate(): Promise<void> {}
}

