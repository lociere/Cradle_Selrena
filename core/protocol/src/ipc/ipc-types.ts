/**
 * IPC协议类型定义
 * 用于内核与Python AI层之间的IPC消息传递。
 */
import { ErrorCode, TraceContext } from "../core";

export enum IPCMessageType {
  // 内核发送到AI层的消息类型
  PERCEPTION_MESSAGE = "perception_message",
  PERCEPTION_CANCEL = "perception_cancel",
  AGENT_PLAN = "agent_plan",
  LIFE_HEARTBEAT = "life_heartbeat",
  MEMORY_SYNC = "memory_sync",
  SHORT_TERM_MEMORY_SYNC = "short_term_memory_sync",
  STATE_SYNC = "state_sync",
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
  vessel_id: string;
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

export interface PerceptionModalityItem {
  modality: PerceptionModalityType;
  text?: string;
  uri?: string;
  mime_type?: string;
  description_hint?: string;
  metadata?: Record<string, any>;
}

export interface ModelInputPayload {
  items: PerceptionModalityItem[];
}

/**
 * 通用感知消息：第三方平台接入统一走该类型。
 * content 中不携带任何 Vessel 私有字段，Soul 层只能读到语义结果。
 */
export interface PerceptionMessageRequest {
  id: string;
  sensoryType: string;
  /** 来源标识，等同于 scene_id */
  source: string;
  timestamp: number;
  /** 熟悉度 0-10，由 Vessel Cortex 计算后注入，Soul 层直接使用 */
  familiarity: number;
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

export interface AgentPlanRequest {
  user_goal: string;
  scene_id?: string;
}

export type IPCKnowledgeScope = "persona" | "general";

export interface IPCKnowledgeRecord {
  entry_id: string;
  scope: IPCKnowledgeScope;
  content: string;
  priority: number;
  tags: string[];
  enabled: boolean;
}

export interface IPCKnowledgeRetrievalConfig {
  persona_top_k: number;
  general_top_k: number;
  min_score: number;
  keyword_weight: number;
  tag_weight: number;
  priority_weight: number;
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
