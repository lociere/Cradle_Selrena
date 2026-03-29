// 这个文件是示例，可以直接删除。
// src/ 下的代码结构由你自定。

/**
 * 【可选】当出站操作较为复杂时，建议提取到此目录。
 * 如果插件逻辑简单，可直接内联在主插件类中处理，无需此目录。
 *
 * ── 设计原则 ──────────────────────────────────────────────────
 *
 * - Handler 通过构造函数参数接受依赖（logger、sender 等），不直接
 *   import 插件 SDK，避免引入循环依赖。
 * - Handler 只负责执行出站操作，不判断是否应该执行（那是主插件类的职责）。
 * - Handler 可被单元测试，不要在此引入导致测试资源加载复杂的其他依赖。
 */

import type { IPluginLogger } from '@cradle-selrena/protocol';
import type { ChannelReplyPayload } from '@cradle-selrena/protocol';

/** 发送消息的函数类型 */
type SendFn = (text: string) => Promise<boolean>;

export class ReplyHandler {
  constructor(
    private readonly _logger: IPluginLogger,
    private readonly _send: SendFn,
  ) {}

  async handle(payload: ChannelReplyPayload): Promise<void> {
    this._logger.debug('[handler] 收到 Soul 回复', { traceId: payload.traceId });

    const sent = await this._send(payload.text);
    if (!sent) {
      this._logger.warn('[handler] 发送失败，客户端未就绪', {
        traceId: payload.traceId,
      });
    }
  }
}
