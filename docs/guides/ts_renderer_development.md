# 渲染交互层开发指南（TS + React）

*语言*: TypeScript、React、Electron Renderer

渲染层负责与用户直接交互，封装 UI 组件、状态管理和与内核通信。应遵循组件化和 MVVM 思想。

## 1. 项目结构
```
packages/renderer/
├── src/
│   ├── App.tsx              # 根组件
│   ├── components/          # 可复用 UI 组件
│   ├── pages/               # 各页面布局
│   ├── store/               # Redux/TanStack 状态管理
│   ├── hooks/               # 自定义 Hook
│   ├── assets/              # 图片/样式等静态资源
│   └── ipc/                 # 与内核的 IPC 封装
├── public/                  # 静态文件
├── tests/                   # 单元/快照测试
└── package.json
```

## 2. 样式与设计
* 使用 `styled-components` 或 `CSS Modules`，避免全局样式污染。
* 遵守设计系统（色彩、间距、控件样式），从 `assets/styles/design-system.ts` 引用。

## 3. 与内核交互
* 通过 `ipcRenderer` 发送事件，封装在 `src/ipc/client.ts`。所有请求需返回 Promise。示例：

```ts
import { send } from '../ipc/client';

const response = await send('kernel:writeFile', { path, content });
```

* 接收事件时使用 `useEffect` 注册监听并在组件卸载时移除。

## 4. 状态管理
* 简单场景可用 React Context，复杂逻辑使用 Redux Toolkit 或 Zustand。
* 所有异步逻辑放在 `store/thunks` 或自定义 Hook。
* 使用 `@reduxjs/toolkit` 的 `createSlice` 规范定义 reducers。

## 5. 测试
* 单元测试使用 Jest + React Testing Library，重点测试逻辑和交互。
* UI 快照用于捕捉无意变更。
* 集成测试可使用 `electron-testing-library` 在真实环境中运行。

## 6. 构建与热加载
* 开发时使用 `vite` 或 `webpack` 的 HMR。
* 生产构建通过 `pnpm build:renderer` 生成静态文件，Electron 在启动时加载。

## 7. 可访问性与国际化
* 保持组件对屏幕阅读器友好，使用 `aria-*` 属性。
* 多语言支持采用 `i18next`，资源文件放在 `locales/`。

## 8. 性能优化
* 避免过多的重渲染，使用 `React.memo` 和 `useCallback`。
* 图片使用懒加载，尽量减少一次性 DOM 大量渲染。
* 对较大列表使用虚拟滚动 (`react-window`)。

## 9. 扩展指南
1. 新页面：在 `pages/` 添加目录并在 `App.tsx` 中注册路由。
2. 公用组件：将样式与逻辑拆分，在 `components/` 创建新模块。
3. IPC 事件：在 `ipc/client.ts` 添加类型定义并更新内核协议。

---

> 渲染层只负责展示和交互，任何业务决策由内核/AI 层处理，请保持组件纯粹并通过事件驱动数据流。