import { randomUUID } from 'crypto';

export interface TraceContext {
  trace_id: string;
}

export function createTraceContext(options?: Partial<TraceContext>): TraceContext {
  return {
    trace_id: options?.trace_id ?? randomUUID(),
  };
}

export enum ErrorCode {
  UNKNOWN = 0,
  CONFIG_ERROR = 100,
  IPC_ERROR = 200,
  IPC_TIMEOUT = 201,
  LIFECYCLE_ERROR = 300,
  EXTENSION_ERROR = 400,
  EXTENSION_VALIDATION_FAILED = 401,
  EXTENSION_SANDBOX_ERROR = 402,
  EXTENSION_PERMISSION_DENIED = 403,
  EXTENSION_LIFECYCLE_ERROR = 404,
  PERSISTENCE_ERROR = 500,
  MEMORY_NOT_FOUND = 501,
  INFERENCE_ERROR = 600,
}

export enum Permission {
  CHAT_SEND = 'CHAT_SEND',
  NATIVE_AUDIO_ASR = 'NATIVE_AUDIO_ASR',
  NATIVE_AUDIO_TTS = 'NATIVE_AUDIO_TTS',
  MEMORY_READ = 'MEMORY_READ',
  MEMORY_WRITE = 'MEMORY_WRITE',
  MEMORY_DELETE = 'MEMORY_DELETE',
  MEMORY_SHORT_TERM = 'MEMORY_SHORT_TERM',
  PERCEPTION_WRITE = 'PERCEPTION_WRITE',
  CONFIG_READ_SELF = 'CONFIG_READ_SELF',
  CONFIG_WRITE_SELF = 'CONFIG_WRITE_SELF',
  CONFIG_READ_GLOBAL = 'CONFIG_READ_GLOBAL',
  EVENT_SUBSCRIBE = 'EVENT_SUBSCRIBE',
  EVENT_PUBLISH = 'EVENT_PUBLISH',
  AGENT_REGISTER = 'AGENT_REGISTER',
  COMMAND_REGISTER = 'COMMAND_REGISTER',
  COMMAND_EXECUTE = 'COMMAND_EXECUTE',
}

export function hasPermission(permission: Permission, grantedPermissions: Permission[]): boolean {
  return grantedPermissions.includes(permission);
}

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

export class ExtensionException extends CoreException {
  constructor(message: string, code: ErrorCode = ErrorCode.EXTENSION_ERROR, trace_id?: string) {
    super(message, code, trace_id);
    Object.setPrototypeOf(this, ExtensionException.prototype);
  }
}

