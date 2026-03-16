/**
 * IPC协议类型定义
 * 用于内核与Python AI层之间的IPC消息传递。
 */
import { ErrorCode, TraceContext } from "../core";

export enum IPCMessageType {
  // 内核发送到AI层的消息类型
  CHAT_MESSAGE = "chat_message",
  LIFE_HEARTBEAT = "life_heartbeat",
  MEMORY_SYNC = "memory_sync",
  STATE_SYNC = "state_sync",
  LOG = "log",  CONFIG_INIT = 'config_init',
  MEMORY_INIT = 'memory_init',
  KNOWLEDGE_INIT = 'knowledge_init',
  // AI层发送到内核的响应/事件类型
  SUCCESS_RESPONSE = "success_response",
  ERROR_RESPONSE = "error_response",
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
export interface ChatMessageRequest {
  user_input: string;
  scene_id: string;
  familiarity?: number;
}

export interface ChatMessageResponse {
  reply_content: string;
  emotion_state: Record<string, any>;
  trace_id: string;
}

export interface LifeHeartbeatResponse {
  thought_content: string;
  emotion_state: Record<string, any>;
  trace_id: string;
}
