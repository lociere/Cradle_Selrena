import { SubAgentProfile } from './mcp';
import { PerceptionEvent } from './perception';

export interface Disposable {
    dispose(): void | Promise<void>;
}

export interface Logger {
    debug(msg: string, ...args: any[]): void;
    info(msg: string, ...args: any[]): void;
    warn(msg: string, ...args: any[]): void;
    error(msg: string, ...args: any[]): void;
}

export interface KeyValueDB {
    get(key: string): Promise<any>;
    set(key: string, value: any): Promise<void>;
    delete(key: string): Promise<void>;
}

export interface PerceptionRegistry {
    /** 将感知事件注入突触母线 */
    inject(event: PerceptionEvent): Promise<void>;
}

export interface SynapseEventBus {
    /** 注册总线监听器，支持流式交互 */
    on(eventName: string, handler: (payload: any) => void): Disposable;
    emit(eventName: string, payload: any): void;
}

export interface AgentManagerRegistry {
    registerSubAgent(profile: SubAgentProfile): Disposable;
}

/** 插件沙箱上下文的核心契约 */
export interface ExtensionContext<TConfig = any> {
    readonly pluginId: string;
    readonly logger: Logger;
    readonly config: TConfig;
    readonly storage: KeyValueDB;
    readonly subscriptions: Disposable[];

    // 核心能力入口点
    readonly perception: PerceptionRegistry;
    readonly bus: SynapseEventBus;
    readonly agents: AgentManagerRegistry;
}

export interface SystemPlugin<TConfig = any> {
    configSchema?: {
        safeParse(input: unknown):
            | { success: true; data: TConfig }
            | { success: false; error: { issues?: Array<{ path?: Array<string | number>; message: string }> } };
    };
    onActivate(ctx: ExtensionContext<TConfig>): Promise<void> | void;
    onDeactivate?(): Promise<void> | void;
}