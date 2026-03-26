/**
 * 主插件类 — src/my-plugin.ts
 *
 * ══════════════════════════════════════════════════════════════════
 *  插件目录结构规范（必须遵守）:
 *
 *  my-plugin/
 *  ├── plugin-manifest.yaml     ← 插件声明（id/name/version/permissions）
 *  ├── index.ts                 ← 入口：export default new MyPlugin()
 *  ├── config/
 *  │   └── schema.ts            ← Zod 配置 Schema + 推断类型
 *  └── src/
 *      ├── my-plugin.ts         ← 本文件：主插件类
 *      ├── handlers/            ← 事件处理器
 *      │   └── reply-handler.ts
 *      └── adapters/            ← Vessel Cortex 适配层
 *          └── platform-normalizer.ts
 *
 *  分层原则：
 *    adapters/ — 平台原始数据 → 标准格式（PerceptionEvent / plain object）
 *    handlers/ — 订阅事件、发送回复等出站动作
 *    my-plugin.ts — 生命周期管理，组合 adapters + handlers
 * ══════════════════════════════════════════════════════════════════
 */

import { BasePlugin } from '@cradle-selrena/plugin-sdk';
import type { ChannelReplyPayload } from '@cradle-selrena/protocol';
import { MyPluginConfig, MyPluginConfigSchema } from '../config/schema';

// 如果是 WebSocket 反向代理适配器，改为继承 WsAdapterPlugin：
// import { WsAdapterPlugin } from '@cradle-selrena/plugin-sdk';

export class MyPlugin extends BasePlugin<MyPluginConfig> {
  constructor() {
    super(MyPluginConfigSchema);
  }

  // ── 生命周期 ──────────────────────────────────────────────────

  protected override async activate(): Promise<void> {
    this.logger.info(
      `[my-plugin] 插件启动，配置: ${JSON.stringify(this.config.features)}`,
    );

    // ── 示例：订阅内核事件 ──────────────────────────────────────
    // this.subscribe() 自动将 disposable 注册到 subscriptions，
    // 插件停止时由 PluginManager 统一释放，无需手动管理。
    this.subscribe('action.channel.reply', (payload) => {
      this._handleReply(payload);
    });

    // ── 示例：注册周期性定时器 ─────────────────────────────────
    // registerInterval() 自动封装定时器并注册进 subscriptions。
    this.registerInterval(() => this._onTick(), 60_000);

    this.logger.info('[my-plugin] 插件启动完成');
  }

  protected override async deactivate(): Promise<void> {
    this.logger.info('[my-plugin] 插件已停止');
    // 通过 registerInterval/registerTimeout/addDisposable 托管的资源由 PluginManager 自动清理
  }

  // ── 私有方法 ────────────────────────────────────────────────

  private _handleReply(payload: ChannelReplyPayload): void {
    this.logger.debug('[my-plugin] 收到回复事件', { traceId: payload.traceId });
    // TODO: 实现具体的回复转发逻辑
  }

  private _onTick(): void {
    this.logger.debug('[my-plugin] 定时心跳');
    // TODO: 实现定时逻辑（如主动感知推送、状态同步等）
  }
}
