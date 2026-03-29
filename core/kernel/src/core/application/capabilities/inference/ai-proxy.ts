/**
 * AIProxy — Python AI 能力的统一 Promise 门面
 * 上层模块仅依赖该门面，不感知 IPC/子进程通信细节。
 */
import {
  AgentPlanRequest,
  AgentPlanResponse,
  ChatMessageResponse,
  LifeHeartbeatRequest,
  LifeHeartbeatResponse,
  PerceptionCancelRequest,
  PerceptionMessageRequest,
} from "@cradle-selrena/protocol";
import { PythonAIManager } from "./python-manager";

export class AIProxy {
  private static _instance: AIProxy | null = null;

  public static get instance(): AIProxy {
    if (!AIProxy._instance) {
      AIProxy._instance = new AIProxy();
    }
    return AIProxy._instance;
  }

  private constructor() {}

  public get isReady(): boolean {
    return PythonAIManager.instance.isReady;
  }

  public async sendPerceptionMessage(request: PerceptionMessageRequest, traceId?: string): Promise<ChatMessageResponse> {
    return PythonAIManager.instance.sendPerceptionMessage(request, traceId);
  }

  public async cancelPerception(request: PerceptionCancelRequest): Promise<void> {
    await PythonAIManager.instance.cancelPerception(request);
  }

  public async requestAgentPlan(request: AgentPlanRequest): Promise<AgentPlanResponse> {
    return PythonAIManager.instance.sendAgentPlan(request);
  }

  public async sendLifeHeartbeat(request: LifeHeartbeatRequest): Promise<LifeHeartbeatResponse> {
    return PythonAIManager.instance.sendLifeHeartbeat(request);
  }
}
