/**
 * Core shared types and utilities for the protocol.
 *
 * 此模块负责定义全局通用异常、错误码、trace context 等基础类型。
 */
import { randomUUID } from "crypto";

/**
 * Trace context，用于全链路追踪。
 */
export interface TraceContext {
  trace_id: string;
}

/**
 * 创建TraceContext（若传入trace_id则复用，否则自动生成）。
 */
export function createTraceContext(options?: Partial<TraceContext>): TraceContext {
  return {
    trace_id: options?.trace_id ?? randomUUID(),
  };
}

/**
 * 错误码枚举，供内核与python层约定。
 */
export enum ErrorCode {
  UNKNOWN = 0,
  CONFIG_ERROR = 100,
  IPC_ERROR = 200,
  IPC_TIMEOUT = 201,
  LIFECYCLE_ERROR = 300,
  PLUGIN_ERROR = 400,
  PLUGIN_VALIDATION_FAILED = 401,
  PLUGIN_SANDBOX_ERROR = 402,
  PLUGIN_PERMISSION_DENIED = 403,
  PLUGIN_LIFECYCLE_ERROR = 404,
  PERSISTENCE_ERROR = 500,
  MEMORY_NOT_FOUND = 501,
  INFERENCE_ERROR = 600,
}

/**
 * 插件权限定义，用于沙箱内插件能力控制。
 */
export enum Permission {
  CHAT_SEND = "CHAT_SEND",
  NATIVE_AUDIO_ASR = "NATIVE_AUDIO_ASR",
  NATIVE_AUDIO_TTS = "NATIVE_AUDIO_TTS",
  MEMORY_READ = "MEMORY_READ",
  MEMORY_WRITE = "MEMORY_WRITE",
  MEMORY_DELETE = "MEMORY_DELETE",
  PERCEPTION_WRITE = "PERCEPTION_WRITE",
  CONFIG_READ_SELF = "CONFIG_READ_SELF",
  CONFIG_WRITE_SELF = "CONFIG_WRITE_SELF",
  CONFIG_READ_GLOBAL = "CONFIG_READ_GLOBAL",
  EVENT_SUBSCRIBE = "EVENT_SUBSCRIBE",
  EVENT_PUBLISH = "EVENT_PUBLISH",
  AGENT_REGISTER = "AGENT_REGISTER",
}

export function hasPermission(permission: Permission, grantedPermissions: Permission[]): boolean {
  return grantedPermissions.includes(permission);
}

/**
 * 核心异常，所有跨模块异常统一使用该类型传递。
 */
export class CoreException extends Error {
  public readonly code: ErrorCode;
  public readonly trace_id?: string;

  constructor(message: string, code: ErrorCode = ErrorCode.UNKNOWN, trace_id?: string) {
    super(message);
    this.code = code;
    this.trace_id = trace_id;
    Object.setPrototypeOf(this, CoreException.prototype);
  }
}

export class PluginException extends CoreException {
  constructor(message: string, code: ErrorCode = ErrorCode.PLUGIN_ERROR, trace_id?: string) {
    super(message, code, trace_id);
    Object.setPrototypeOf(this, PluginException.prototype);
  }
}
