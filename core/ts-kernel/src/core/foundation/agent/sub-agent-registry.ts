import { SubAgentProfile } from '@cradle-selrena/protocol';

export interface RegisteredAgent {
  extensionId: string;
  profile: SubAgentProfile;
}

/**
 * Sub-Agent 鍏ㄥ眬娉ㄥ唽琛ㄣ€?
 * 鎻掍欢閫氳繃 ctx.agents.registerSubAgent() 灏?SubAgentProfile 鍐欏叆姝ゅ锛?
 * Python AI 灞傦紙閫氳繃 IPC锛夋垨 TS 璋冨害鍣ㄥ彲浠庢澶勮幏鍙栧彲鐢?Agent 娓呭崟銆?
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

  public register(extensionId: string, profile: SubAgentProfile): void {
    const key = `${extensionId}:${profile.name}`;
    this._agents.set(key, { extensionId, profile });
  }

  public unregister(extensionId: string, agentName: string): void {
    this._agents.delete(`${extensionId}:${agentName}`);
  }

  public getAll(): RegisteredAgent[] {
    return Array.from(this._agents.values());
  }

  public getByExtension(extensionId: string): RegisteredAgent[] {
    return this.getAll().filter((a) => a.extensionId === extensionId);
  }

  public findByName(agentName: string): RegisteredAgent | undefined {
    return this.getAll().find((a) => a.profile.name === agentName);
  }
}

