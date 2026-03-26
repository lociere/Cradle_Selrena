import { Disposable } from './sandbox';
import { z } from 'zod';

export interface MCPTool<TArgs = any> {
    name: string;
    description: string;
    parameters: z.ZodType<TArgs>;
    handler: (args: TArgs) => Promise<any> | any;
}

export interface SubAgentProfile {
    id: string;
    name: string;
    /** 给主脑用于路由 Agent 的描述 */
    description: string;
    /** 该 Agent 注册时携带的 MCP 级别工具 */
    tools: MCPTool[];
    /** 执行操作后是否允许影响主脑的情绪/生成长期记忆 (联觉纠缠) */
    memoryImpact?: boolean;
    /** 是否可以在生命周期中主动打断正在进行的流 */
    allowInterrupt?: boolean;
}

export interface AgentRegistry {
    registerSubAgent(profile: SubAgentProfile): Disposable;
}