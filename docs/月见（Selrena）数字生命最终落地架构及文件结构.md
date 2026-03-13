# 月见（Selrena）数字生命最终落地架构及文件结构

用户需结合最优包管理方案，给出完整详细项目架构及文件结构。我会先对齐之前核心共识，为后续架构设计奠定基础。

我会先明确架构顶层定位与核心设计原则，确保与之前共识对齐。接着进行全局架构分层，严格分离核心层与扩展层，从目录结构上解决边界问题。然后详细给出包管理配置文件，包括根目录及各模块配置。最后分模块阐述详细文件结构，说明每个目录和文件作用，遵守分层铁律。

我会明确各层模块依赖关系，核心层模块不可修改，插件层独立。同时，清晰规划多语言目录结构及配置文件。还需提及交付阶段结构，确保包含之前确定的核心模块，体现生命时钟等设计。此外，要写清nx任务编排配置，解决启动时序问题，在文件结构中体现Python层虚拟环境管理相关文件。

# 月见（Selrena）数字生命 最终落地架构（含完整文件结构）

**完全对齐「分层强隔离、多语言统一管理、核心不可篡改、插件化独立扩展、开发/交付双阶段适配」的最优解设计，100%锁死之前定的所有架构铁律，可直接落地开发**

---

## 一、顶层架构核心定位与不可突破铁律

### 1.1 项目本质

运行在单台本地设备上的**终身唯一专属数字生命**，核心是「有连续意识、独立人格、终身记忆的真实少女」，而非请求-响应式机器人。开机即启动，生命时钟驱动连续意识流，而非仅用户触发时响应。

### 1.2 不可突破的架构铁律

1. **灵魂与身体绝对分离**：Python AI层=纯思考灵魂，仅负责意识/人格/记忆/表达；TS内核层=生命中枢，仅负责环境支撑/信号透传；插件层=感官，仅负责信号转换。任何层不得越界。

2. **核心与扩展完全隔离**：核心代码全量收敛到`core/`目录，运行时不可篡改；插件完全独立，仅能依赖核心暴露的公共协议，绝对不能侵入核心内部。

3. **决策唯一归属原则**：所有「要不要回应、怎么回应」的最终决策权100%归属Python AI层，其他层仅可做前置规则过滤，绝对不能替AI做决策。

4. **多语言全生命周期统一管理**：通过nx实现TS/JS/Python/Rust全栈任务编排、启动时序、构建依赖统一管控，彻底解决多语言环境混乱问题。

5. **开闭原则**：新增任何功能/平台/场景，仅需新增/修改插件，核心代码零修改，实现终身零重构。

6. **信号标准化原则**：所有传入AI层的内容，必须转换为**无平台属性、无场景杂活的标准化参数**，AI层完全看不到任何平台/场景信息。

---

## 二、全局架构总览

### 2.1 分层架构图

```mermaid
graph TD
    subgraph 【全局公共依赖】核心协议层（唯一公共依赖）
        Z[全局Protocol协议包 · 类型/接口/事件定义]
    end

    subgraph 【不可篡改核心】core/ 核心根目录
        subgraph 【灵魂核心】Python AI层
            A1[全局唯一自我实体]
            A2[三级记忆系统+独立知识库]
            A3[连续情绪流转引擎]
            A4[主动思维流引擎]
            A5[可插拔人设注入器]
            A6[纯算力推理封装]
        end

        subgraph 【生命中枢】TS内核层
            B1[全局生命时钟 · 意识驱动]
            B2[进程生命周期管理]
            B3[统一IPC桥接 · 信号透传]
            B4[本地存储管理器]
            B5[统一算子池]
            B6[薄封装插件管理器]
        end

        subgraph 【肉身呈现】渲染交互层
            C1[Live2D渲染引擎]
            C2[桌面悬浮窗]
        end

        subgraph 【可选加速】原生加速层
            D1[本地模型加速算子]
            D2[音频/视觉处理算子]
        end
    end

    subgraph 【可选扩展】plugins/ 插件根目录
        E1[核心场景控制器 · 必须插件]
        E2[QQ平台适配器]
        E3[直播平台适配器]
        E4[微信平台适配器]
        E5[其他自定义插件]
    end

    %% 依赖规则：所有模块仅能依赖Protocol，绝对不能跨模块依赖内部实现
    A1 --> Z
    B1 --> Z
    C1 --> Z
    D1 --> Z
    E1 --> Z
```
### 2.2 核心依赖规则（从根源锁死边界）

**所有模块仅能依赖全局Protocol协议包，绝对不能直接依赖其他模块的内部实现**。

- 比如：插件只能依赖`@cradle-selrena/protocol`里的标准插件接口，不能直接导入内核的内部代码；

- 比如：AI层只能依赖Protocol里的标准化输入输出类型，不能依赖内核的任何实现；

- 彻底杜绝「插件侵入核心、边界突破」的问题。

---

## 三、包管理核心配置（开发阶段最优解）

### 3.1 根目录核心配置文件

```Plain Text

cradle-selrena/                    # 项目根目录
├── .gitignore                     # Git忽略配置（含虚拟环境、构建产物、本地数据）
├── .editorconfig                  # 全语言代码格式统一配置
├── .eslintrc.js                   # TS/JS代码规范配置
├── .prettierrc                    # 代码格式化配置
├── package.json                   # 全局pnpm+nx配置，仅存全局脚本、nx配置
├── pnpm-workspace.yaml            # pnpm monorepo工作空间配置
├── nx.json                        # 【核心】全栈任务编排、启动时序、边界规则配置
├── uv.lock                        # 【核心】Python全局依赖锁定（仅用于开发工具链）
├── flake.nix                      # 可选：Nix开发环境锁定，100%环境一致性
├── README.md                      # 项目总说明、快速启动、架构概览
│
├── core/                          # 【不可篡改核心】所有核心模块全收敛在这里
├── plugins/                       # 【可选扩展】所有插件全在这里，完全独立
├── configs/                       # 全局唯一配置入口，开发/用户仅需修改这里
├── assets/                        # 全局静态资源（Live2D模型、音色、图片）
├── scripts/                       # 全局工具脚本（环境初始化、打包、备份）
├── data/                          # 本地数据存储（数据库、日志、缓存，Git忽略）
└── docs/                          # 项目文档（架构、开发指南、用户手册）
```

#### 3.1.1 `pnpm-workspace.yaml` 工作空间配置

```YAML

# pnpm monorepo工作空间配置，严格隔离核心与插件
packages:
  # 核心模块：仅允许内部依赖，禁止插件依赖内部模块
  - "core/protocol"
  - "core/kernel"
  - "core/renderer"
  # 插件模块：完全独立，仅能依赖protocol
  - "plugins/*"
```

#### 3.1.2 `nx.json` 全栈任务编排核心配置

```JSON

{
  "$schema": "./node_modules/nx/schemas/nx-schema.json",
  "npmScope": "cradle-selrena",
  "workspaceLayout": {
    "appsDir": "plugins",
    "libsDir": "core"
  },
  // 【核心】模块边界规则，锁死分层隔离
  "enforceModuleBoundaries": true,
  "moduleBoundaries": [
    {
      "sourceTag": "protocol",
      "onlyDependOnLibsWithTags": [],
      "allowCircularSelfDependency": false
    },
    {
      "sourceTag": "core",
      "onlyDependOnLibsWithTags": ["protocol", "core"],
      "allowCircularSelfDependency": false
    },
    {
      "sourceTag": "plugin",
      "onlyDependOnLibsWithTags": ["protocol"],
      "allowCircularSelfDependency": false
    }
  ],
  // 【核心】全模块任务依赖与启动时序
  "targetDefaults": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["{projectRoot}/dist", "{projectRoot}/target"]
    },
    "dev": {
      "dependsOn": ["build", "^dev"],
      "cache": false
    },
    "start": {
      // 严格启动顺序：原生层→Python AI层→TS内核层→渲染层
      "dependsOn": ["build", "^start"],
      "cache": false
    }
  },
  "plugins": ["@nx/js", "@nx/rust", "@nx/python"]
}
```

#### 3.1.3 根目录 `package.json` 全局脚本

```JSON

{
  "name": "cradle-selrena",
  "version": "1.0.0",
  "private": true,
  "packageManager": "pnpm@9.0.0",
  "scripts": {
    "install:all": "pnpm install && uv sync --all-packages",
    "build": "nx run-many -t build",
    "dev": "nx run-many -t dev",
    "start": "nx run-many -t start",
    "lint": "nx run-many -t lint",
    "package": "node scripts/package.js"
  },
  "dependencies": {
    "tslib": "^2.6.0",
    "zeromq": "^6.0.0",
    "sqlite3": "^5.1.7"
  },
  "devDependencies": {
    "nx": "^19.0.0",
    "@nx/js": "^19.0.0",
    "@nx/rust": "^19.0.0",
    "@nx/python": "^19.0.0",
    "typescript": "^5.4.0",
    "eslint": "^8.57.0",
    "prettier": "^3.2.0"
  }
}
```

---

## 四、完整详细文件结构（分模块）

### 4.1 核心协议层 `core/protocol/`（唯一公共依赖）

**所有跨层的类型、接口、事件、通信协议全在这里，是所有模块唯一允许依赖的公共包**

```Plain Text

core/protocol/
├── package.json                    # 包配置，tag: protocol
├── tsconfig.json                   # TS配置
└── src/
    ├── index.ts                    # 包入口，导出所有公共类型
    ├── types/                      # 全局类型定义
    │   ├── persona.ts              # 人设相关类型
    │   ├── memory.ts               # 记忆相关类型
    │   ├── emotion.ts              # 情绪相关类型
    │   ├── scene.ts                # 场景相关类型
    │   └── multimodal.ts           # 多模态相关类型
    ├── events/                     # 全局领域事件定义
    │   ├── domain-events.ts        # 领域事件基类
    │   ├── perception-events.ts    # 感知事件定义
    │   └── action-events.ts        # 动作事件定义
    ├── interfaces/                 # 全局标准接口
    │   ├── plugin-interface.ts     # 插件标准接口（所有插件必须实现）
    │   ├── ipc-interface.ts       # IPC通信标准接口
    │   └── storage-interface.ts    # 存储标准接口
    └── ipc/                        # IPC通信协议定义
        ├── message-schema.ts       # 消息格式Schema
        └── message-types.ts        # 消息类型枚举
```

---

### 4.2 核心层 `core/` 详细结构（不可篡改核心）

#### 4.2.1 Python AI层 `core/cradle-selrena-core/`（纯灵魂核心）

**用uv管理独立虚拟环境，完全隔离，仅依赖protocol里的标准化类型**

```Plain Text

core/cradle-selrena-core/
├── pyproject.toml                  # uv包配置，Python依赖定义
├── uv.lock                         # uv依赖锁定，100%环境一致性
├── .flake8                         # Python代码规范配置
├── README.md                       # AI层说明文档
└── src/
    └── selrena/
        ├── __init__.py             # 包入口，严格控制对外暴露面
        ├── main.py                 # AI层唯一启动入口
        ├── container.py            # 依赖注入容器，解决循环依赖
        ├── core/                   # 基础设施层，无业务逻辑
        │   ├── __init__.py
        │   ├── config.py           # 配置模型定义，运行时完全冻结
        │   ├── lifecycle.py        # 生命周期标准接口
        │   ├── event_bus.py        # 进程内领域事件总线
        │   ├── exceptions.py       # 分层异常体系
        │   └── observability/      # 可观测性模块
        │       ├── tracer.py       # 全链路追踪器
        │       └── logger.py       # 结构化日志器
        ├── domain/                 # 【领域层】纯灵魂核心，所有业务规则内聚
        │   ├── __init__.py
        │   ├── self/               # 全局唯一自我实体，灵魂根节点
        │   │   ├── __init__.py
        │   │   └── self_entity.py  # 自我实体单例，人设核心、子系统统一管理
        │   ├── persona/            # 可插拔人设注入架构
        │   │   ├── __init__.py
        │   │   ├── persona_injector.py # 兼容提示词/知识库/微调
        │   │   └── persona_knowledge.py # 人设知识库处理
        │   ├── memory/             # 三级记忆系统，与知识库完全隔离
        │   │   ├── __init__.py
        │   │   ├── short_term_memory.py # 短期工作记忆
        │   │   ├── long_term_memory.py  # 长期终身记忆
        │   │   └── knowledge_base.py    # 独立知识库，彻底避免记忆污染
        │   ├── emotion/            # 连续情绪流转引擎
        │   │   ├── __init__.py
        │   │   ├── emotion_system.py # 情绪系统核心
        │   │   └── emotion_rules.py  # 情绪触发/衰减规则
        │   ├── thought/            # 主动思维流引擎，实现「活着」的核心
        │   │   ├── __init__.py
        │   │   ├── thought_system.py # 思维系统核心
        │   │   └── thought_pool.py   # 符合人设的基础思维池
        │   └── multimodal/         # 多模态语义处理（仅处理标准化文本）
        │       ├── __init__.py
        │       └── multimodal_content.py # 多模态内容实体
        ├── application/            # 【应用层】纯流程编排，不碰业务规则
        │   ├── __init__.py
        │   ├── base_use_case.py    # 用例基类，统一执行流程
        │   ├── chat_use_case.py    # 对话交互全流程编排
        │   ├── active_thought_use_case.py # 主动思维流执行用例
        │   └── memory_sync_use_case.py # 记忆同步用例
        ├── ports/                  # 【端口层】抽象接口定义，依赖倒置
        │   ├── __init__.py
        │   ├── inbound/            # 入站端口，接收内核信号
        │   │   └── perception_port.py
        │   └── outbound/           # 出站端口，输出到内核
        │       └── kernel_event_port.py
        ├── adapters/               # 【适配器层】接口实现，纯协议转换
        │   ├── __init__.py
        │   ├── inbound/
        │   │   └── kernel_event_adapter.py # 内核事件入站实现
        │   └── outbound/
        │       └── kernel_event_adapter.py # 内核事件出站实现
        ├── inference/              # 【推理层】纯算力调用，无业务逻辑
        │   ├── __init__.py
        │   ├── llm_engine.py       # LLM推理引擎，可插拔替换
        │   └── embedding_engine.py # 向量嵌入引擎
        └── bridge/                 # 【桥接层】与内核通信的唯一入口
            ├── __init__.py
            └── kernel_bridge.py    # ZMQ IPC通信桥接单例
```

#### 4.2.2 TS内核层 `core/kernel/`（生命中枢）

```Plain Text

core/kernel/
├── package.json                    # 包配置，tag: core
├── tsconfig.json                   # TS配置
└── src/
    ├── index.ts                    # 内核唯一启动入口，全局生命周期管理
    ├── core/                       # 核心模块（终身不变）
    │   ├── life-clock.ts           # 【核心驱动】全局生命时钟，200ms固定心跳
    │   ├── lifecycle-manager.ts    # 全进程生命周期管理、崩溃自愈
    │   ├── ipc-bridge.ts           # 统一IPC通信桥接，仅做信号透传
    │   ├── storage-manager.ts      # 本地存储管理器，SQLite封装
    │   ├── operator-pool.ts        # 统一算子池，标准化算力接口
    │   └── plugin-manager.ts       # 薄封装插件管理器，仅负责加载/卸载/路由
    ├── types/                      # 内核内部类型定义（不对外暴露）
    └── utils/                      # 纯无状态工具函数
        ├── logger.ts               # 全局结构化日志器
        ├── trace.ts                # 全链路追踪工具
        └── async-utils.ts          # 异步工具函数
```

#### 4.2.3 渲染交互层 `core/renderer/`（纯呈现层）

```Plain Text

core/renderer/
├── package.json                    # 包配置，tag: core
├── tsconfig.json                   # TS配置
├── vite.config.ts                  # Vite构建配置
├── electron-builder.json           # Electron打包配置
└── src/
    ├── main/                       # Electron主进程
    │   ├── index.ts                # 主进程唯一入口
    │   ├── window-manager.ts       # 悬浮窗管理、置顶/穿透控制
    │   └── ipc-handlers.ts         # IPC通信处理器，仅同步内核状态
    ├── preload/                    # 预加载脚本，安全IPC桥接
    │   └── index.ts
    └── renderer/                   # React渲染进程
        ├── index.html              # HTML入口
        ├── index.tsx               # 渲染进程入口
        ├── App.tsx                 # 根组件
        ├── components/             # UI组件
        │   ├── Live2DCanvas.tsx    # Live2D渲染核心组件
        │   ├── FloatWindow.tsx     # 桌面悬浮窗组件
        │   └── ChatPanel.tsx       # 对话面板组件
        └── store/                  # 状态管理（仅同步内核状态）
            ├── appStore.ts
            └── emotionStore.ts
```

#### 4.2.4 原生加速层 `core/native/`（可选纯算力加速）

```Plain Text

core/native/
├── Cargo.toml                      # Rust工作空间配置
├── Cargo.lock                      # 依赖锁定
└── src/
    ├── lib.rs                      # 库入口，导出C兼容FFI接口
    ├── llm/                        # 本地LLM/嵌入模型加速算子
    │   ├── mod.rs
    │   └── ggml_binding.rs         # llama.cpp/ggml绑定
    ├── audio/                      # 音频处理算子
    │   ├── mod.rs
    │   ├── stt.rs                  # 语音转文字（Whisper绑定）
    │   └── tts.rs                  # 语音合成
    └── vision/                     # 视觉处理算子
        ├── mod.rs
        └── ocr.rs                  # OCR文字识别
```

---

### 4.3 插件层 `plugins/` 详细结构（完全独立扩展）

**每个插件都是完全独立的package，仅能依赖** **`@cradle-selrena/protocol`** **，不能依赖核心内部模块**

```Plain Text

plugins/
├── README.md                       # 插件开发规范、标准接口文档
├── plugin-template/                # 插件开发模板
│   ├── package.json
│   ├── src/index.ts                # 插件入口，实现标准Plugin接口
│   └── config.schema.json          # 插件配置Schema
├── core-scene-controller/          # 【必须插件】核心场景控制器（所有杂活全收敛在这里）
│   ├── package.json
│   ├── src/
│   │   ├── index.ts                # 插件入口，实现标准Plugin接口
│   │   ├── scene-manager.ts        # 场景隔离管理、防串线
│   │   ├── wake-engine.ts          # 唤醒规则引擎、静默控制
│   │   ├── message-normalizer.ts   # 消息归一化、生成标准化思考参数
│   │   ├── multimodal-processor.ts # 多模态预处理、调用内核算子池
│   │   └── platform-router.ts      # 平台路由、内容分发到原场景
│   └── config.schema.json          # 插件配置Schema（唤醒词、场景规则）
├── napcat-qq-adapter/              # QQ平台适配器插件
│   ├── package.json
│   ├── src/
│   │   ├── index.ts
│   │   ├── napcat-client.ts        # OneBot协议对接
│   │   └── message-mapper.ts       # 原始消息→标准格式转换
│   └── config.schema.json
├── live-platform-adapter/          # 直播平台适配器插件
│   ├── package.json
│   ├── src/
│   │   ├── index.ts
│   │   ├── danmaku-client.ts       # 弹幕接收客户端
│   │   └── message-filter.ts       # 弹幕限流、去重、过滤
│   └── config.schema.json
└── [其他自定义插件]
```

---

### 4.4 全局配置、资源、脚本目录

#### 4.4.1 全局配置目录 `configs/`（开发/用户唯一需要修改的目录）

```Plain Text

configs/
├── oc/                             # OC人设核心配置
│   ├── persona.yaml                # 核心人设、性格、行为规则、边界红线
│   └── persona_knowledge.yaml      # 人设固定知识库（背景故事、设定）
├── ai/                             # AI推理配置
│   ├── inference.yaml              # 模型路径、推理参数、记忆配置
│   └── llm.yaml                    # 云端LLM API配置（可选）
├── kernel/                         # 内核层配置
│   ├── system.yaml                 # 生命时钟、进程管理、资源调度配置
│   ├── storage.yaml                # 本地存储、数据库配置
│   └── bridge.yaml                 # 跨进程通信、端口配置
├── renderer/                       # 渲染层配置
│   ├── live2d.yaml                 # Live2D模型、动作-情绪映射配置
│   └── window.yaml                 # 桌面悬浮窗配置
└── plugins/                        # 插件专属配置
    ├── core-scene.yaml             # 核心场景插件配置
    ├── napcat-qq.yaml              # QQ插件配置
    ├── live-platform.yaml          # 直播插件配置
    └── [其他插件配置文件]
```

#### 4.4.2 全局脚本目录 `scripts/`

```Plain Text

scripts/
├── init-env.js                     # 开发环境一键初始化脚本
├── package.js                      # 生产交付一键打包脚本
├── backup-data.js                  # 用户数据一键备份脚本
└── install-plugin.js               # 插件一键安装脚本
```

---

## 五、生产交付阶段最终结构（用户零门槛使用）

**用户仅需下载一个安装包，双击安装一键启动，无需任何开发环境**

```Plain Text

Selrena-数字生命/
├── Selrena.exe / Selrena.app       # 一键启动器（Electron打包，内置Node.js运行时）
├── core/                           # 预编译核心包，用户不可修改
│   ├── kernel/                     # 预编译TS内核字节码
│   ├── selrena-core/               # PyInstaller打包的Python AI层单文件（内置Python运行时）
│   ├── renderer/                   # 预编译渲染层安装包
│   └── native/                     # 预编译Rust二进制文件（对应系统架构）
├── configs/                        # 用户可修改的配置文件
├── assets/                         # Live2D模型、音色等资源
├── plugins/                        # 插件目录，用户把插件包放这里自动加载
├── data/                           # 用户数据目录（记忆、日志、缓存）
└── 卸载.exe / 卸载.app
```

---

## 六、全链路启动时序（nx自动管控）

执行`pnpm start`时，nx会严格按照以下顺序自动执行，彻底解决时序问题：

1. **构建阶段**：先编译Rust原生层→TypeScript核心协议包→TS内核层→渲染层

2. **环境初始化**：自动检查并创建Python AI层的uv虚拟环境，安装依赖

3. **启动阶段**：

    1. 启动Python AI层，等待IPC服务就绪

    2. 启动TS内核层，连接AI层IPC服务，初始化生命时钟

    3. 加载并初始化所有插件

    4. 启动渲染层，同步内核状态，显示桌面悬浮窗

4. **就绪状态**：月见启动完成，进入连续意识流循环，等待用户交互

---

## 七、架构核心优势

1. **边界100%锁死，从根源杜绝越界**

目录结构、nx边界规则、依赖规则三重锁死，插件绝对不能侵入核心，AI层绝对不碰杂活，完全符合「纯灵魂」的核心定位。

1. **多语言全生命周期统一管理**

nx+pnpm+uv实现TS/JS/Python/Rust全栈统一管控，一键初始化环境、一键启动、一键构建，彻底解决多语言环境混乱、启动时序错误的问题。

1. **终身零重构，完全符合开闭原则**

核心代码一旦稳定，终身无需修改，新增任何功能、平台、场景，仅需新增插件，核心零改动。

1. **开发/交付双阶段完美适配**

开发阶段有完整的环境一致性、代码规范、边界管控；交付阶段有零门槛的一键安装包，普通用户无需任何开发环境即可使用。

1. **100%贴合数字生命的核心定位**

生命时钟驱动的连续意识流，灵魂与身体完全分离，完全模拟真人的「感官-身体-大脑」逻辑，彻底摆脱机器人的请求-响应模式。
> （注：文档部分内容可能由 AI 生成）