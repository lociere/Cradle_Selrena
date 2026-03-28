# 插件开发指南

## 必须存在的文件

| 文件 | 说明 |
|---|---|
| `plugin-manifest.yaml` | 插件声明，PluginManager 据此加载 |
| `package.json` | 包配置，`main` 必须指向 `dist/index.js` |
| `tsconfig.json` | 照抄模板，无需修改 |
| `index.ts` | 入口，`export default new MyPlugin()` |
| `config/schema.ts` | Zod 配置 Schema，用户配置从这里读取 |

主体代码放在 `src/` 下，**内部如何组织完全由你决定**。

---

## plugin-manifest.yaml 字段说明

```yaml
id: my-plugin          # 必须与目录名一致，格式 [a-z0-9-]
name: My Plugin
version: 0.1.0
author: Your Name
description: 一句话描述
main: dist/index.js    # 固定值，不要修改
minAppVersion: 0.1.0

# 自由标签，仅用于分类展示，不影响内核行为
tags:
  - adapter            # 参考: adapter / tool / sense / action / schedule / audio / ui / ...

# 只声明真正用到的权限
permissions:
  - CONFIG_READ_SELF
  # - PERCEPTION_WRITE     向 Soul 注入感知事件
  # - EVENT_SUBSCRIBE      订阅全局事件总线
  # - EVENT_PUBLISH        发布事件（限 plugin.<id>.* 命名空间）
  # - CHAT_SEND            发送消息
  # - NATIVE_AUDIO_ASR     调用 ASR
  # - NATIVE_AUDIO_TTS     调用 TTS
  # - AGENT_REGISTER       注册 Sub-Agent / MCP 工具
  # - MEMORY_READ          读取插件短期记忆
  # - MEMORY_WRITE         写入插件短期记忆
```

---

## 插件类 API 速查

```typescript
// 继承基类（WebSocket 反向代理场景继承 WsAdapterPlugin）
class MyPlugin extends BasePlugin<MyPluginConfig> {

  protected async activate(): Promise<void> { ... }
  protected async deactivate(): Promise<void> { ... }

  // ── 内置辅助方法（资源自动注入 subscriptions，插件停止时自动释放） ──
  this.subscribe(eventName, handler)
  this.registerInterval(fn, ms)
  this.registerTimeout(fn, ms)

  // ── 沙箱上下文 ctx ──
  this.ctx.perception.inject(event)         // 向 Soul 注入感知（fire-and-forget）
  this.ctx.bus.on(eventName, handler)       // 订阅事件总线
  this.ctx.bus.emit(eventName, payload)     // 发布事件
  this.ctx.agents.registerSubAgent(profile) // 注册 Sub-Agent / MCP 工具
  this.ctx.shortTermMemory.append(entry)    // 写入短期记忆
  this.ctx.shortTermMemory.getRecent(...)   // 读取短期记忆
  this.ctx.storage.get/set/delete(key)      // KV 持久化存储
  this.ctx.config                           // 已解析的配置对象
  this.ctx.logger / this.logger             // 插件专属日志
}
```

---

## 新建插件

```bash
# 复制模板
cp -r plugins/_template plugins/my-new-plugin

# 改 id：plugin-manifest.yaml → id / package.json → name
# 编写逻辑：src/ 目录随意组织

# 编译
pnpm --filter @cradle-selrena/my-new-plugin build

# 启用：configs/plugin/enabled-plugins.yaml 添加 - my-new-plugin
```


---

## 1. 强制文件结构

```
<plugin-id>/                       ← 目录名即插件 id，格式 [a-z0-9-]
├── plugin-manifest.yaml            ← 【必须】插件声明文件
├── package.json                    ← 【必须】npm 包配置
├── tsconfig.json                   ← 【必须】TS 编译配置（照抄模板，不要改）
├── index.ts                        ← 【必须】入口：export default new MyPlugin()
├── config/
│   └── schema.ts                   ← 【必须】Zod 配置 Schema
└── src/
    └── <plugin-id>.ts              ← 【必须】主插件类（文件名可自定义）
```

> **dist/**（编译产物）由 `tsc` 自动生成，不要手动修改或提交。

---

## 2. 可选子目录

根据插件类型按需创建，不需要的目录**不要创建**。

```
src/
├── cortex/          仅平台适配器插件需要（Vessel Cortex 数据清洗层）
│   ├── <proto>-normalizer.ts   协议帧 → CortexOutput 归一化
│   ├── <proto>-types.ts        平台私有类型（禁止泄露到 Soul）
│   └── message-parser.ts       消息段结构化解析
│
├── tools/           仅 MCP 工具插件需要
│   ├── <tool-name>.tool.ts     工具定义（handler + schema）
│   └── index.ts                统一 export
│
├── tasks/           仅主动感知 / 定时插件需要
│   └── <task-name>.task.ts     定时任务 / 事件驱动推送
│
└── utils/           任何插件均可使用（纯工具函数，无副作用）
    └── <helpers>.ts
```

---

## 3. 插件类型与推荐架构

### 类型 A：**平台适配器**（adapter tags）

接入外部平台（QQ、Discord、Minecraft 等）并向 Soul 注入感知事件。

```
继承：WsAdapterPlugin（WebSocket 反向代理）或 BasePlugin（HTTP / 轮询）

src/
├── <name>-plugin.ts       主类：继承 WsAdapterPlugin，实现 onJsonMessage()
└── cortex/
    ├── <proto>-normalizer.ts  帧归一化 → CortexOutput
    ├── <proto>-types.ts        平台私有类型定义
    └── message-parser.ts       消息段解析
```

**数据流：** 平台 WS 帧 → `onJsonMessage()` → `cortex/` 归一化 → `ctx.perception.inject()` → Soul

**关键约束：**
- 平台私有字段（QQ 号、群组 ID 等）必须在 `cortex/` 内被清洗/替换为通用字段，严禁通过 `PerceptionEvent.content` 上传至 Soul。
- `cortex/` 层的函数只通过返回值传递结果，不调用 `ctx`。

---

### 类型 B：**工具插件**（tool tags）

为 Soul 提供可调用的 MCP 工具（函数调用）。

```
继承：BasePlugin

src/
├── <name>-plugin.ts       主类：在 activate() 中注册工具
└── tools/
    ├── search.tool.ts      工具 1：定义 schema + handler
    └── index.ts            统一 export
```

**数据流：** Soul 调用 → Sub-Agent → `tools/` handler 执行 → 结构化结果返回

```typescript
// activate() 示例
const disposable = this.ctx.agents.registerSubAgent({
  id: 'search-agent',
  name: '搜索代理',
  description: '搜索互联网信息',
  tools: [searchTool],
});
this.ctx.subscriptions.push(disposable);
```

---

### 类型 C：**主动感知插件**（sense tags）

定时或事件驱动地向 Soul 推送感知事件（如天气、提醒、系统状态）。

```
继承：BasePlugin

src/
├── <name>-plugin.ts       主类：在 activate() 中注册定时器
└── tasks/
    └── weather.task.ts    定时任务：获取数据、构造 PerceptionEvent
```

**数据流：** 定时器触发 → `tasks/` 构造数据 → `ctx.perception.inject()` → Soul

```typescript
// activate() 示例
this.registerInterval(() => this._pushWeather(), 30 * 60_000); // 每 30 分钟
```

---

### 类型 D：**UI / 渲染插件**（ui tags）

与渲染层（Live2D、窗口等）交互，不直接与 Soul 通信。

```
继承：BasePlugin

src/
└── <name>-plugin.ts   订阅 ActionStream 事件，驱动渲染层状态机
```

---

## 4. 生命周期规范

```typescript
// 启动：activate() 是所有初始化的入口
protected override async activate(): Promise<void> {
  // 所有资源托管到 subscriptions，插件停止时自动释放：
  this.subscribe(...)         // 自动 push 到 subscriptions
  this.registerInterval(...)  // 自动 push 到 subscriptions
  this.ctx.subscriptions.push(someDisposable)  // 手动托管
}

// 停止：deactivate() 只负责平台资源（WS 连接、文件句柄等）
protected override async deactivate(): Promise<void> {
  // subscriptions 内的资源由 PluginManager 在此之后统一释放，无需手动处理
  await super.deactivate(); // WsAdapterPlugin 继承时必须调用
}
```

---

## 5. 配置文件规范

用户配置存放于 `configs/plugin/<plugin-id>.yaml`（运行时由 PluginManager 注入）。

```yaml
# configs/plugin/my-plugin.yaml
server:
  host: 127.0.0.1
  port: 8080

features:
  enabled: true
```

Schema 中所有字段必须提供 `.default()`，确保用户配置文件可以部分留空。

---

## 6. 核心约束清单

| 约束 | 说明 |
|---|---|
| **Soul-Vessel 边界** | 平台私有字段（QQ 号等）严禁出现在 `PerceptionEvent.content` 中 |
| **Cortex 无副作用** | `cortex/` 层只做数据转换，不调用 `ctx`，不写日志，不触发 IO |
| **Fire-and-forget** | `ctx.perception.inject()` 立即返回，AI 回复通过 `action.channel.reply` 事件异步接收 |
| **无类型 dict 禁止** | 跨模块边界只传递 Pydantic/Zod 模型或具名 interface，禁止裸 `object` / `any` |
| **最小权限** | `plugin-manifest.yaml` 中只声明实际用到的权限 |
| **配置不可变** | 配置在 `activate()` 时已冻结，运行时不要修改 `this.config` |

---

## 7. 新建插件步骤

```bash
# 1. 复制模板
cp -r plugins/_template plugins/my-new-plugin

# 2. 修改以下文件：
#    plugin-manifest.yaml  → 改 id/name/description/tags/permissions
#    package.json          → 改 name 字段
#    config/schema.ts      → 改为实际配置字段
#    src/my-plugin.ts      → 改为实际插件逻辑和类名
#    index.ts              → 改 import 的类名

# 3. 编译
pnpm --filter @cradle-selrena/<plugin-id> build

# 4. 启用插件
# 编辑 configs/plugin/enabled-plugins.yaml，添加 - my-new-plugin
```
