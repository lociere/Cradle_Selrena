/**
 * ══════════════════════════════════════════════════════════════════
 *  插件文件结构规范（强制）
 * ══════════════════════════════════════════════════════════════════
 *
 *  my-plugin/                     ← 目录名即插件 id（[a-z0-9-]）
 *  ├── plugin-manifest.yaml        ← 【必须】插件声明
 *  ├── package.json                ← 【必须】包配置
 *  ├── tsconfig.json               ← 【必须】TS 编译配置（锁定为此模板的值）
 *  ├── index.ts                    ← 【必须】入口：export default new MyPlugin()
 *  ├── config/
 *  │   └── schema.ts               ← 【必须】Zod 配置 Schema
 *  └── src/
 *      └── my-plugin.ts            ← 【必须】主插件类（本文件，可自由命名）
 *
 *  ── 可选子目录（按实际需要创建，不需要则不创建）──────────────────
 *
 *  src/
 *  ├── cortex/                     ← 【仅平台适配器需要】Vessel Cortex 层
 *  │   │  职责：平台原始协议 → 标准 PerceptionEvent，不含任何业务判断
 *  │   ├── <protocol>-normalizer.ts    原始帧归一化
 *  │   ├── <protocol>-types.ts         平台私有类型定义（禁止泄露到 Soul）
 *  │   └── message-parser.ts           消息段解析
 *  │
 *  ├── tools/                      ← 【仅 MCP 工具插件需要】工具定义
 *  │   │  职责：声明 MCPTool，由 Agent 执行后返回结构化结果
 *  │   ├── <tool-name>.tool.ts
 *  │   └── index.ts                    统一 export 所有 tools
 *  │
 *  ├── tasks/                      ← 【仅主动感知/定时插件需要】定时任务
 *  │   │  职责：定时/事件驱动地向 Soul 推送感知，或执行出站操作
 *  │   └── <task-name>.task.ts
 *  │
 *  └── utils/                      ← 【可选】纯工具函数（无副作用）
 *      └── <helpers>.ts
 *
 *  ══════════════════════════════════════════════════════════════════
 *  分层原则（关键）
 *  ══════════════════════════════════════════════════════════════════
 *
 *  cortex/  仅做数据转换，不含业务决策，所有输出通过返回值传递，
 *           绝不直接调用 ctx。平台私有字段（如 QQ 号、群号）必须
 *           在此层清洗/重命名为通用字段后丢弃，严禁上传至 Soul。
 *
 *  tools/   纯函数风格，handler 不依赖插件状态，依赖通过参数传入。
 *
 *  tasks/   持有必要状态（定时器 ID、上次执行时间等），通过
 *           ctx.perception.inject() 向 Soul 推送，fire-and-forget。
 *
 *  src/my-plugin.ts  生命周期管理：组合以上各模块，持有 ctx 引用，
 *           是唯一允许调用 ctx.perception / ctx.bus / ctx.agents 的地方。
 */

import { BasePlugin } from '@cradle-selrena/plugin-sdk';
import type { ChannelReplyPayload } from '@cradle-selrena/protocol';
import { MyPluginConfig, MyPluginConfigSchema } from '../config/schema';

// ── 如果是 WebSocket 反向代理适配器，改为继承 WsAdapterPlugin：
// import { WsAdapterPlugin } from '@cradle-selrena/plugin-sdk';
// export class MyPlugin extends WsAdapterPlugin<MyPluginConfig> { ... }
//   然后在 activate() 里调用 this.startWsServer(host, port, accessToken)
//   并实现 onJsonMessage(data) 处理入站消息帧。

export class MyPlugin extends BasePlugin<MyPluginConfig> {
  constructor() {
    super(MyPluginConfigSchema);
  }

  // ── 生命周期 ──────────────────────────────────────────────────

  protected override async activate(): Promise<void> {
    this.logger.info(`[my-plugin] 插件启动`, { features: this.config.features });

    // ── 范式 A：订阅内核事件（所有插件类型均可使用）─────────────
    //
    // subscribe() 返回的 disposable 会被自动注册到 ctx.subscriptions，
    // 插件停止时 PluginManager 统一释放，无需手动管理。
    this.subscribe('action.channel.reply', (payload) => {
      this._handleReply(payload);
    });

    // ── 范式 B：注册周期性定时器（sense / action 类插件）────────
    //
    // registerInterval() 自动将定时器封装为 disposable 并注入 subscriptions。
    // this.registerInterval(() => this._pushPerception(), 60_000);

    // ── 范式 C：注册 MCP 工具（tool 类插件）─────────────────────
    //
    // const disposable = this.ctx.agents.registerSubAgent({
    //   id: 'my-tool-agent',
    //   name: '工具代理',
    //   description: '提供 xxx 能力，用于 yyy 场景',
    //   tools: [myTool],
    // });
    // this.ctx.subscriptions.push(disposable);

    // ── 范式 D：向 Soul 注入感知事件（adapter / sense 类插件）───
    //
    // 需要权限：PERCEPTION_WRITE
    // ctx.perception.inject() 是 fire-and-forget，立即返回。
    // AI 回复通过订阅 'action.channel.reply' 事件异步接收。
    //
    // this.ctx.perception.inject({
    //   id: crypto.randomUUID(),
    //   source: 'plugin:my-plugin',
    //   sensoryType: 'TEXT',
    //   content: { text: '...', modality: ['text'], familiarity: 5 },
    //   timestamp: Date.now(),
    // });

    this.logger.info('[my-plugin] 插件启动完成');
  }

  protected override async deactivate(): Promise<void> {
    // 通过 registerInterval / registerTimeout / ctx.subscriptions.push 托管的
    // 所有资源由 PluginManager 在此之后统一释放，无需手动清理。
    this.logger.info('[my-plugin] 插件已停止');
  }

  // ── 私有方法 ─────────────────────────────────────────────────

  private _handleReply(payload: ChannelReplyPayload): void {
    this.logger.debug('[my-plugin] 收到 Soul 回复', { traceId: payload.traceId });
    // TODO: 根据 traceId 查找原始请求的路由信息，执行出站操作（发消息等）
  }
}
