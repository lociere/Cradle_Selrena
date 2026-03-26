import { SubAgentProfile } from '@cradle-selrena/protocol';

export interface RegisteredAgent {
  pluginId: string;
  profile: SubAgentProfile;
}

/**
 * Sub-Agent 全局注册表。
 * 插件通过 ctx.agents.registerSubAgent() 将 SubAgentProfile 写入此处，
 * Python AI 层（通过 IPC）或 TS 调度器可从此处获取可用 Agent 清单。
 */
export class SubAgentRegistry {
  private static _instance: SubAgentRegistry | null = null;
  private readonly _agents: Map<string, RegisteredAgent> = new Map();

  public static get instance(): SubAgentRegistry {
    if (!SubAgentRegistry._instance) {
      SubAgentRegistry._instance = new SubAgentRegistry();
    }
    return SubAgentRegistry._instance;
  }

  private constructor() {}

  public register(pluginId: string, profile: SubAgentProfile): void {
    const key = `${pluginId}:${profile.name}`;
    this._agents.set(key, { pluginId, profile });
  }

  public unregister(pluginId: string, agentName: string): void {
    this._agents.delete(`${pluginId}:${agentName}`);
  }

  public getAll(): RegisteredAgent[] {
    return Array.from(this._agents.values());
  }

  public getByPlugin(pluginId: string): RegisteredAgent[] {
    return this.getAll().filter((a) => a.pluginId === pluginId);
  }

  public findByName(agentName: string): RegisteredAgent | undefined {
    return this.getAll().find((a) => a.profile.name === agentName);
  }
}
