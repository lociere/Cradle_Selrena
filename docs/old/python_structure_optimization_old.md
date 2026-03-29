# Python AI 核心文件结构优化说明

## 当前架构 vs 文档架构对比分析

### 发现的问题

1. **文档结构过于简化**：缺少了实际架构中的关键分层
2. **实际架构更完善**：采用了 DDD（领域驱动设计）分层架构
3. **部分文件命名不一致**：如 `event_bus.py` vs `event_bus_client.py`

### 优化后的完整文件结构

```
cradle-selrena-core/
├── pyproject.toml          # PEP 621 现代 Python 包标准配置
├── requirements.txt        # 依赖锁定文件（pip-compile 生成）
├── README.md              # Python 包说明文档
├── src/
│   └── cradle_selrena_core/
│       ├── __init__.py     # 包入口，严格控制导出
│       ├── main.py         # 进程唯一入口，生命周期管理
│       ├── container.py    # 依赖注入容器（解决循环依赖）
│       
│       # ========== 核心基础设施层（Core Infrastructure）==========
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config_manager.py   # 配置管理（从内核同步）
│       │   ├── event_bus_client.py # 事件总线客户端（与 TS 内核通信）
│       │   ├── ai_service.py       # AI 服务（连接 TS 与 Python 的桥梁）
│       │   └── main_service.py     # 主服务协调器
│       
│       # ========== 适配器层（Adapters）==========
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── zmq/                # ZeroMQ 事件总线适配器
│       │   │   ├── __init__.py
│       │   │   └── event_bus.py
│       │   └── legacy_backup/      # 旧架构备份（逐步迁移）
│       │       └── cradle/
│       │           └── core/
│       │               └── config_manager.py
│       
│       # ========== 领域层（Domain）- 核心灵魂模型 ==========
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── persona.py          # 人设模型（四层人格结构）
│       │   ├── memory.py           # 记忆模型（episodic/semantic/procedural）
│       │   └── emotion.py          # 情感状态模型
│       
│       # ========== 数据模型层（Schemas）==========
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── events.py           # 事件模型（与 protocol 对齐）
│       │   ├── payloads.py         # 事件载荷模型
│       │   ├── domain.py           # 内部领域模型
│       │   └── configs/            # 配置模型
│       │       ├── __init__.py
│       │       ├── system.py       # 系统配置模型
│       │       └── soul.py         # 灵魂配置模型
│       
│       # ========== 应用服务层（Application）- 用例编排 ==========
│       ├── application/
│       │   ├── __init__.py
│       │   ├── conversation.py     # 对话服务编排
│       │   ├── memory_service.py   # 记忆服务编排
│       │   └── reasoning.py        # 推理服务编排
│       
│       # ========== 工具层（Utils）==========
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── async_utils.py      # 异步/线程池工具
│       │   ├── config.py           # 配置加载工具
│       │   ├── dicts.py            # 字典工具
│       │   ├── env.py              # 环境变量工具
│       │   ├── event_payload.py    # 事件载荷工具
│       │   ├── exceptions.py       # 标准化异常体系
│       │   ├── logger.py           # 统一结构化日志
│       │   ├── path.py             # 路径处理工具
│       │   ├── string.py           # 字符串工具
│       │   └── yaml_io.py          # YAML 读写工具
│       
│       # ========== 人设核心层（Persona）==========
│       ├── persona/
│       │   ├── __init__.py
│       │   ├── profile.py          # 核心人设档案管理
│       │   ├── emotion.py          # 情感状态模拟器
│       │   ├── prompt_builder.py   # 动态 Prompt 构建
│       │   ├── consistency.py      # 人设一致性校验/防 OOC
│       │   └── finetune/           # LoRA 人设微调模块
│       │       └── __init__.py
│       
│       # ========== 记忆系统（Memory）==========
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── user_profile.py     # 用户结构化画像库
│       │   ├── episodic.py         # 情节记忆库
│       │   ├── knowledge.py        # 人设知识库/RAG 检索
│       │   ├── skill.py            # 技能记忆库
│       │   └── retriever.py        # 混合检索引擎
│       
│       # ========== 意图理解（Intention）==========
│       ├── intention/
│       │   ├── __init__.py
│       │   ├── parser.py           # 用户意图解析
│       │   ├── decision.py         # 决策生成引擎
│       │   └── task_planner.py     # 任务拆解与规划
│       
│       # ========== MCP Agent ==========
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── mcp_client.py       # MCP 协议客户端
│       │   ├── tool_registry.py    # 工具元数据注册
│       │   └── command_generator.py # 指令生成器
│       
│       # ========== 推理引擎层（Inference）==========
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── llm.py              # LLM 推理引擎
│       │   ├── audio.py            # 音频推理引擎（TTS/STT）
│       │   ├── vision.py           # 视觉推理引擎
│       │   ├── engines/        # 多模态引擎池
│       │   │   ├── __init__.py
│       │   │   ├── base.py         # 统一引擎抽象接口
│       │   │   ├── embedded.py     # 本地嵌入式引擎
│       │   │   ├── remote.py       # 远程云端引擎
│       │   │   ├── router.py       # 引擎路由选择器
│       │   │   └── utils/          # 引擎工具
│       │   │       ├── preprocessor.py    # 数据预处理
│       │   │       └── prompt_builder.py  # Prompt 构建
│       │   └── scheduler/          # 智能推理调度器
│       │       ├── __init__.py
│       │       ├── router.py       # 推理任务路由
│       │       ├── load_monitor.py # 硬件负载监控
│       │       └── cache.py        # 推理结果缓存
│       
│       └── ports/                  # 端口层（接口定义）
│           └── __init__.py
│           
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_soul_core.py
    │   └── test_napcat_adapter.py
    ├── integration/
    │   └── __init__.py
    └── e2e/
        └── __init__.py
```

## 架构分层说明

### 1. 核心基础设施层（core/）
- **职责**：提供 AI 核心运行所需的基础设施
- **关键组件**：
  - `config_manager.py`：配置管理，从 TS 内核同步配置
  - `event_bus_client.py`：事件总线客户端，与 TS 内核通信
  - `ai_service.py`：AI 服务，封装 AI 核心能力供 TS 调用
  - `main_service.py`：主服务协调器，协调各服务

### 2. 适配器层（adapters/）
- **职责**：适配外部系统和协议
- **关键组件**：
  - `zmq/event_bus.py`：ZeroMQ 事件总线适配器
  - `legacy_backup/`：旧架构备份，逐步迁移

### 3. 领域层（domain/）
- **职责**：核心领域模型，DDD 的灵魂层
- **关键组件**：
  - `persona.py`：人设模型
  - `memory.py`：记忆模型
  - `emotion.py`：情感模型

### 4. 数据模型层（schemas/）
- **职责**：Pydantic 数据模型定义
- **关键组件**：
  - `events.py`：事件模型
  - `payloads.py`：载荷模型
  - `configs/`：配置模型

### 5. 应用服务层（application/）
- **职责**：用例编排，组合领域能力
- **关键组件**：
  - `conversation.py`：对话服务
  - `memory_service.py`：记忆服务
  - `reasoning.py`：推理服务

### 6. 工具层（utils/）
- **职责**：通用工具函数，无业务耦合
- **特点**：无外界 IO，纯工具函数

### 7. 业务核心层（persona/, memory/, intention/, agent/）
- **职责**：纯 AI 逻辑，数字生命核心能力
- **特点**：无任何外界交互，纯业务逻辑

### 8. 推理引擎层（inference/）
- **职责**：多模态推理引擎
- **架构**：
  - 引擎池（engines/，原名 engine_pool）：统一抽象接口
  - 调度器（scheduler/）：智能负载调度

## 架构优势

1. **DDD 分层清晰**：领域层、应用层、基础设施层职责明确
2. **依赖倒置**：上层依赖抽象接口，不依赖具体实现
3. **开闭原则**：新增能力通过扩展实现，无需修改核心代码
4. **单一职责**：每个模块职责单一，易于维护和测试
5. **可替换性**：引擎池设计支持无缝替换底层实现

## 下一步优化

1. ✅ 更新文档结构描述
2. 🔄 迁移 `legacy_backup` 中的配置管理功能
3. 🔄 完善 `ports/` 层的接口定义
4. 🔄 补充单元测试覆盖率
5. 🔄 优化 `inference/` 层的引擎池实现
