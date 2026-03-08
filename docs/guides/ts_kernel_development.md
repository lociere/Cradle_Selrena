# 系统内核层开发指南（TS）

*语言*: TypeScript (Electron 主进程 + Node.js)

本指南针对运行在内核进程的代码，负责进程管理、协议实现、权限控制、硬件调度等。**绝不包含任何 AI 或人设逻辑**，所有语义处理由 Python AI 核心层完成。

## 1. 代码结构
```
packages/kernel/
├── src/
│   ├── main.ts              # 启动入口，创建 Electron App
│   ├── kernel-service.ts    # 内核主服务
│   ├── events/              # 事件定义与广播
│   ├── plugins/             # 动态加载插件，例如 websocket、HTTP
│   ├── utils/               # 通用工具函数
│   └── types/               # 协议 TypeScript 类型
├── tests/                   # 单元/集成测试
└── package.json
```

## 2. 核心职责
- 管理 Electron 进程生命周期（`app.on('ready')` 等）。
- 维护全局事件总线：使用 `EventEmitter` 封装 `send/receive`，同时与 Python AI 通过 WebSocket 或 IPC 交互。
- 权限系统：`kernel-service.ts` 应有 `checkPermission(actor, action)` 方法，所有外部请求先经过验证。
- 硬件调度：音频编解码、摄像头权限、GPU 资源，都由此层统一调度并转发给 Renderer 或 Python。
- 插件机制：`plugins/` 下的模块应导出 `activate(context)` 函数，在启动时按配置动态加载。

## 3. 类型与协议
* 所有消息类型由 `protocol/` 目录生成，自动同步到 Python；禁止手动修改。
* 使用 `ts-node` 开发时可直接引入类型，编译时使用 `pnpm build` 生成 `dist/`。

```ts
import { KernelEvent } from '../types/kernel';

eventBus.emit('user.input', { text: 'hi' } as KernelEvent);
```

## 4. 异步与错误处理
* 使用 `async/await`，并在顶层使用 `try/catch` 捕获。不要在未处理的 `Promise` 上直接 `.catch()`。记录错误到 `logs/kernel.log`。
* 对于 Electron IPC 调用，HTTP 请求等需设置超时并优雅失败。

## 5. 测试与 CI
* 单元测试使用 Jest；浏览器内核相关可用 `electron-mocha`。
* CI 脚本在 `package.json` 中定义 `test`、`lint`、`build`。
* 提交前运行 `pnpm lint` + `pnpm test:unit`。

## 6. 代码风格
* 开启 `strict` 模式。
* 命名遵循驼峰式，文件使用小写短横线。
* 对外暴露 API 在 `src/api.ts` 集中维护，内部模块通过依赖注入获取服务。

## 7. 性能与安全
* 不要在主线程执行大量 CPU 任务，可使用 `worker_threads` 或交给 Rust 后端。
* 输入数据必须经过严格校验，防止注入或拒绝服务攻击。
* 不暴露调试端口到生产环境。

## 8. 扩展指南
1. 添加新事件：在 `src/events/index.ts` 定义并更新 `protocol/` 生成脚本。
2. 新服务：在 `kernel-service.ts` 创建类并在 `main.ts` 实例化。
3. 插件：实现 `activate(context)`，在 `packages/kernel/plugins/index.ts` 注册。

---

> 核心层只负责协议与系统管理，任何 AI/人设需求请通过事件总线发送到 Python 核心处理。