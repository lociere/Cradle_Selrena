/**
 * IPC协议类型定义
 * 用于内核与Python AI层之间的IPC消息传递。
 */
import { ErrorCode, TraceContext } from "../core";
import type { PerceptionModalitySemantic, PerceptionModalityItem } from "../generated";

export enum IPCMessageType {
  // 内核发送到AI层的消息类型
  PERCEPTION_MESSAGE = "perception_message",
  PERCEPTION_CANCEL = "perception_cancel",
  AGENT_PLAN = "agent_plan",
  AGENT_SYNTHESIS = "agent_synthesis",
  LIFE_HEARTBEAT = "life_heartbeat",
  MEMORY_SYNC = "memory_sync",
  SHORT_TERM_MEMORY_SYNC = "short_term_memory_sync",
  STATE_SYNC = "state_sync",
  CONSOLIDATE_MEMORY = "consolidate_memory",
  LOG = "log",  CONFIG_INIT = 'config_init',
  MEMORY_INIT = 'memory_init',
  KNOWLEDGE_INIT = 'knowledge_init',
  // AI层发送到内核的响应/事件类型
  SUCCESS_RESPONSE = "success_response",
  ERROR_RESPONSE = "error_response",
}

/**
 * IPC消息分类：用于日志、路由和扩展时保持语义清晰。
 */
export enum IPCMessageCategory {
  PERCEPTION = "perception",
  COGNITION = "cognition",
  INFERENCE = "inference",
  SYNC = "sync",
  CONTROL = "control",
  OBSERVABILITY = "observability",
  RESPONSE = "response",
}

export interface IPCRequest {
  type: IPCMessageType;
  trace_id: string;
  payload: any;
}

export interface IPCResponse {
  type: IPCMessageType;
  trace_id: string;
  success: boolean;
  payload?: any;
  data?: any;
  error?: {
    code: ErrorCode;
    message: string;
  };
}

// 将 payload 兼容为 data
export function normalizeResponse(response: IPCResponse): IPCResponse {
  if (response.payload !== undefined && response.data === undefined) {
    response.data = response.payload;
  }
  return response;
}

export function createIPCRequest(type: IPCMessageType, trace_id: string, payload: any = {}): IPCRequest {
  return { type, trace_id, payload };
}

export function createSuccessResponse(type: IPCMessageType, trace_id: string, payload: any = {}): IPCResponse {
  return { type, trace_id, success: true, payload, data: payload };
}

export function createErrorResponse(
  type: IPCMessageType,
  trace_id: string,
  code: ErrorCode,
  message: string
): IPCResponse {
  return {
    type,
    trace_id,
    success: false,
    error: { code, message },
  };
}

// 下面是常用的业务类型定义（可根据需要扩展）

export type MessageSourceType = "private" | "group" | "channel" | "terminal" | "system" | "unknown";
export type SceneSessionPolicy = "by_source" | "by_actor";

export type PerceptionModalityType = "text" | "image" | "video";

/**
 * 上游来源元数据：只保留跨平台通用字段，禁止平台私有协议字段进入AI层。
 */
export interface MessageSourceMeta {
  adapter_id: string;
  source_type: MessageSourceType;
  source_id: string;
}

export interface MessageActorMeta {
  actor_id: string;
  actor_name?: string;
}

export interface SceneRoutingHint {
  session_policy?: SceneSessionPolicy;
  actor?: MessageActorMeta;
}

// PerceptionModalitySemantic & PerceptionModalityItem 由 generated/ 契约定义，此处 re-export 保持向后兼容
export type { PerceptionModalitySemantic, PerceptionModalityItem };

export interface ModelInputPayload {
  items: PerceptionModalityItem[];
}

/**
 * 通用感知消息：第三方平台接入统一走该类型。
 * content 中不携带任何适配器私有字段，AI Core 只能读到语义结果。
 */
export interface PerceptionMessageRequest {
  id: string;
  sensoryType: string;
  /** 来源标识，等同于 scene_id */
  source: string;
  timestamp: number;
  /** 熟悉度 0-10，由适配器归一化层计算后注入，AI Core 直接使用 */
  familiarity: number;
  /**
   * 寻址模式：由适配器归一化层从平台信号中计算，屏蔽平台细节。
   * direct  — 明确呼唤月见（唤醒词、@、私聊）；AI Core 预期给出回复
   * ambient — 焦点窗口内的环境感知；月见可自主选择是否开口
   */
  address_mode: 'direct' | 'ambient';
  content: {
    /**
     * 注入 LLM 的完整上下文文本（含对话背景前缀）。
     * 内核层不应对此字段做任何平台特定的字符串解析。
     */
    text?: string;
    modality: string[];
    /** 结构化多模态项（文本 + 图片 URI + 视频 URI 等） */
    items?: PerceptionModalityItem[];
  };
}

export interface PerceptionCancelRequest {
  scene_id: string;
  target_trace_id: string;
  reason?: string;
}

export interface ChatMessageResponse {
  reply_content: string;
  emotion_state: Record<string, any>;
  trace_id: string;
}

/**
 * 工具描述符
 * 由 TS 层将当前已注册的 MCP 工具清单传入 Python AI 层用于规划。
 */
export interface ToolDescriptor {
  /** 工具唯一名称，格式建议：namespace.action，例如 workspace.search */
  name: string;
  /** 工具作用的一句话说明（供 LLM 理解） */
  description: string;
  /** 参数名称列表（可选，供 LLM 生成 arguments_hint） */
  parameters?: string[];
}

export interface AgentPlanRequest {
  user_goal: string;
  scene_id?: string;
  /** 当前可用工具清单（由内核从 MCP 注册表注入） */
  available_tools?: ToolDescriptor[];
}

export interface AgentSynthesisRequest {
  original_goal: string;
  scene_id?: string;
  /** 工具执行结果列表 */
  tool_results: AgentToolResult[];
  trace_id?: string;
}

export interface AgentToolResult {
  tool_name: string;
  status: "success" | "error" | "skipped";
  /** JSON 序列化的结果内容 */
  result_json: string;
}

export interface AgentSynthesisResponse {
  reply_content: string;
  emotion_state: Record<string, any>;
  trace_id: string;
}

export type IPCKnowledgeScope = "persona" | "knowledge";

export interface IPCKnowledgeRecord {
  entry_id: string;
  /** 知识范围：persona = PersonaInjector 编译消费 | knowledge = KnowledgeBase 管理 */
  scope: IPCKnowledgeScope;
  /** 编译分组（仅 scope=persona 有效） */
  compile_group: string;
  content: string;
  priority: number;
  enabled: boolean;
}

export interface IPCKnowledgeRetrievalConfig {
  mode: "full_injection" | "semantic_rag";
  top_k: number;
  min_score: number;
  semantic_weight: number;
}

export interface IPCKnowledgeBaseInitPayload {
  version: string;
  retrieval: IPCKnowledgeRetrievalConfig;
  entries: IPCKnowledgeRecord[];
}

export interface KnowledgeInitRequest {
  knowledge_base: IPCKnowledgeBaseInitPayload;
}

export interface MCPToolSuggestion {
  tool_name: string;
  purpose: string;
  confidence: number;
  arguments_hint?: Record<string, any>;
}

export interface AgentPlanResponse {
  summary: string;
  reasoning: string;
  suggestions: MCPToolSuggestion[];
  trace_id: string;
}

export interface LifeHeartbeatRequest {
  attention_mode: "standby" | "ambient" | "focused";
}

export interface LifeHeartbeatResponse {
  thought_content: string;
  emotion_state: Record<string, any>;
  trace_id: string;
}

/** v4.5 记忆固化请求 — 由生命时钟空闲触发器发起 */
export interface ConsolidateMemoryRequest {
  scene_id: string;
  reason: 'idle_timeout' | 'zone_b_pressure';
  trace_id?: string;
}

export interface ConsolidateMemoryResponse {
  consolidated_count: number;
  trace_id: string;
}

export interface TTSSynthesizeRequest {
  text: string;
  output_path?: string;
}

export interface TTSSynthesizeResponse {
  status: "success" | "failed" | "error";
  output_path?: string;
  message?: string;
}

export interface ASRRecognizeRequest {
  audio_path: string;
}

export interface ASRRecognizeResponse {
  status: "success" | "error";
  text?: string;
  message?: string;
}
