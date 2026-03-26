/**
 * Handler 示例 — src/handlers/reply-handler.ts
 *
 * Handler 层职责：
 *   - 订阅内核事件（如 action.channel.reply）
 *   - 执行出站操作（发送消息、调用外部 API 等）
 *   - 不直接接触原始协议数据（那是 adapters 的职责）
 *
 * Handler 接受 logger 等依赖作为构造函数参数（依赖注入），
 * 不直接 import 插件 SDK，避免循环依赖。
 *
 * 用法：
 *   const handler = new ReplyHandler(this.logger);
 *   this.subscribe('action.channel.reply', (p) => handler.handle(p));
 */

import type { IPluginLogger } from '@cradle-selrena/protocol';

interface ReplyEventPayload {
  trace_context?: { trace_id?: string };
  reply_content?: string;
}

export class ReplyHandler {
  private readonly _logger: IPluginLogger;

  constructor(logger: IPluginLogger) {
    this._logger = logger;
  }

  handle(payload: unknown): void {
    const p = payload as ReplyEventPayload | undefined;
    this._logger.debug('[handler] 收到回复', {
      traceId: p?.trace_context?.trace_id,
    });
    // TODO: 执行具体的出站动作
  }
}
