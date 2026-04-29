# Avatar Renderer Shell

此处为月见数字生命的“物理躯壳”与“视觉本体”实现层。

当前仓库内已提供一个可运行的原生壳占位进程：

- `pnpm --filter @cradle-selrena/renderer-avatar start`
- `pnpm avatar`

它会以原生头像壳身份连接内核 `AvatarEngineController`，持续发送 `status/heartbeat`，并把收到的最新视觉指令写入：

- `runtime/temp/avatar-shell-state.json`

这不是 Unity + Live2D 正式实现，但它已经把“内核动作流 → 原生头像壳协议”跑通，后续替换为真正 Unity 工程时，无需再改内核协议。

## 架构定位
* **角色**：内置 Native Avatar 引擎，是真正的“提线木偶”（无边框透明窗口、Live2D 模型展现、高性能口型同步）。
* **驱动方式**：由 `core/ts-kernel` 的 `AvatarEngineController` 发送 WebSocket 动作、音频流与情绪等 `VisualCommand` 进行直接同步。不负责任何大模型调用和决策业务。
* **技术栈**：基于 Unity + Cubism SDK + uLipSync 的高性能双生独立进程。

## 当前边界
这层属于月见原生身体的一部分，不属于插件系统。

现阶段它的职责不是直接提供最终 Unity 工程资源，而是先稳定以下边界：

- Kernel 到 Avatar Shell 的协议面
- 视觉命令与音频推送的消费方式
- 原生头像壳的心跳与状态上报方式

等真正 Unity + Live2D 工程接入时，应保持这条边界稳定，替换实现而不是重新设计宿主协议。
