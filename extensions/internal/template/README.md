# Extension Template

这个模板用于创建新的 Cradle Selrena extension。

## 文件结构

- extension-manifest.yaml: 扩展清单。
- package.json: 包元数据与构建脚本。
- tsconfig.json: TypeScript 构建配置。
- index.ts: 扩展入口，导出 `defineExtension(...)`。
- config/schema.ts: Zod 配置模型。
- src/my-extension.ts: 主扩展类。

## 最小入口

```ts
import { defineExtension } from '@cradle-selrena/extension-sdk';
import { MyExtension } from './src/my-extension';

export default defineExtension({
  manifest: {
    activationEvents: ['onStartup'],
  },
  extension: new MyExtension(),
});
```

## manifest 示例

```yaml
id: my-extension
name: My Extension
version: 0.1.0
author: Your Name
description: Example extension scaffold for Cradle Selrena.
main: dist/index.js
minAppVersion: 0.1.0
tags:
  - tool
permissions:
  - CONFIG_READ_SELF
```

## 常用能力

- `BaseExtension<TConfig>`: 标准扩展基类。
- `WsAdapterExtension<TConfig>`: 适用于需要内建 WebSocket 服务的 adapter extension。
- `this.subscribe(topic, handler)`: 订阅事件总线。
- `this.registerCommand(id, handler, metadata)`: 注册命令。
- `this.registerInterval(fn, ms)` / `this.registerTimeout(fn, ms)`: 注册自动清理的定时器。
- `this.ctx.perception.inject(event)`: 向 AI Core 注入标准化感知事件。
- `this.ctx.shortTermMemory.*`: 访问扩展短期记忆。
- `this.ctx.storage.*`: 访问扩展 KV 存储。

## 使用模板创建新扩展

```bash
cp -r extensions/internal/template extensions/adapters/my-new-extension
```

复制后需要改这些内容：

- extension-manifest.yaml 中的 `id`、`name`、`description`
- package.json 中的包名
- index.ts 中的命令 ID
- config/schema.ts 中的配置模型
- src 下的具体业务实现

## 架构边界

- Adapter extension 负责协议清洗和归一化。
- AI Core 只接收标准消息与感知事件。
- 自定义事件统一使用 `extension.<id>.*` 命名空间。
- 平台私有字段不要直接泄露到 AI Core。