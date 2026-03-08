# Cradle Selrena Core 架构重构总结

## 重构日期
2026 年 3 月 7 日

## 重构目标
按照 `Cradle-Selrena：终极完美架构（TS-Rust 无缝升级）.md` 文档要求，重构 Python AI 核心目录结构，实现：
- ✅ 清晰的架构分层
- ✅ 依赖倒置原则
- ✅ 接口抽象（TS/Rust 无缝替换）
- ✅ 最小可用 AI 核心实现

## 重构前结构（已删除）
```
❌ bus/              # 重复实现，已合并到 ports
❌ core/             # 职责不清，已拆分到各层
❌ soul/             # 架构过深，已重构为 domain + application
❌ synapse/          # 过度设计，已简化为 ports 事件
❌ vessel/           # 职责越界，已移至 adapters
❌ intention/        # 功能冗余，已合并到 application
❌ memory/           # 重复实现，已移至 domain
❌ persona/          # 重复实现，已移至 domain
```

## 重构后结构（符合文档）
```
cradle_selrena_core/
├── core/                # ✅ 基础设施层：配置、事件、服务
│   ├── __init__.py
│   ├── config_manager.py  # 配置管理
│   ├── event_bus_client.py  # 事件总线客户端
│   ├── ai_service.py      # AI 服务
│   └── main_service.py    # 主服务协调器
│
├── domain/              # ✅ 领域层：核心业务模型
│   ├── __init__.py
│   ├── persona.py       # 人设模型（四层人格）
│   ├── memory.py        # 记忆模型（类型/重要性）
│   └── emotion.py       # 情感模型（分类/强度）
│
├── application/         # ✅ 应用层：用例编排
│   ├── __init__.py
│   ├── conversation.py  # 对话服务
│   ├── memory_service.py # 记忆服务
│   └── reasoning.py     # 推理服务
│
├── ports/              # ✅ 端口层：标准接口
│   ├── __init__.py
│   ├── kernel.py        # 内核端口（KernelPort）
│   ├── memory.py        # 记忆端口（MemoryPort）
│   └── persona.py       # 人设端口（PersonaPort）
│
├── adapters/           # ✅ 适配层：接口实现
│   ├── __init__.py
│   ├── kernel.py        # 内核适配器（适配 TS/Rust）
│   ├── memory.py        # 记忆适配器（文件系统）
│   └── persona.py       # 人设适配器（YAML 配置）
│
├── inference/          # ✅ 推理层：多模态能力
│   ├── __init__.py
│   ├── llm.py          # LLM 后端（OpenAI/本地）
│   ├── vision.py       # 视觉后端（抽象接口）
│   └── audio.py        # 音频后端（STT/TTS）
│
├── schemas/            # ✅ 模式层：协议模型（已存在）
│   ├── domain/         # 领域模型 Schema
│   ├── protocol/       # 通信协议 Schema
│   └── configs/        # 配置 Schema
│
├── utils/              # ✅ 工具层：通用工具（已存在）
│   ├── logger.py
│   ├── path.py
│   └── ...
│
├── container.py        # ✅ AI 核心容器（统一入口）
├── main.py             # ✅ 演示入口
└── examples/           # ✅ 使用示例
    └── basic_usage.py
```

## 核心实现

### 1. Domain Layer（领域层）
- **Persona**: 四层人格结构（Identity/Values/Behavior/Expression）
- **Memory**: 记忆类型（Episodic/Semantic/Procedural）+ 重要度 + 情感标签
- **Emotion**: 情感分类 + 强度 + 效价 + 唤醒度 + 衰减机制

### 2. Application Layer（应用层）
- **ConversationService**: 对话流程编排（接收→检索→构建→生成→记忆→发送）
- **MemoryService**: 记忆管理（编码/存储/检索/遗忘）
- **ReasoningService**: 多模态推理（文本/视觉/语音）

### 3. Ports Layer（端口层）
- **KernelPort**: 内核接口（发送消息/播放音频/截图/文件读写）
- **MemoryPort**: 记忆存储接口（保存/检索/删除）
- **PersonaPort**: 人设配置接口（加载/保存）

### 4. Adapters Layer（适配层）
- **KernelAdapter**: 当前适配 TS 内核（通过事件总线）
- **MemoryAdapter**: 文件系统实现（JSON 存储）
- **PersonaAdapter**: YAML 配置实现

### 5. Inference Layer（推理层）
- **LLMBackend**: 抽象基类
  - **OpenAILLM**: OpenAI 兼容 API
  - **LocalLLM**: 本地 GGUF 模型（llama-cpp-python）
- **VisionBackend**: 视觉理解接口（Image Caption/OCR）
- **AudioBackend**: 语音接口（STT/TTS）

### 6. Container（容器）
- **AIContainer**: 统一入口 + 依赖注入 + 生命周期管理
- **global_ai_container**: 全局单例
- **get_container()**: 获取容器实例

## 架构优势

### 1. 零耦合
- AI 核心不依赖任何具体内核实现（TS/Rust）
- 所有外部依赖通过 `ports` 层抽象

### 2. 可替换
- 实现同一套 `KernelPort` 接口，TS→Rust 无缝替换
- 业务代码零改动

### 3. 可测试
- 所有接口可轻松 Mock
- 领域层无外部依赖，单元测试简单

### 4. 可扩展
- 新功能通过插件化方式接入
- 遵循开闭原则（对扩展开放，对修改关闭）

### 5. 普适性
- 符合 Clean Architecture 最佳实践
- 符合依赖倒置原则（DIP）

## 使用示例

### 基本对话
```python
from cradle_selrena_core import AIContainer

container = AIContainer(config_dir, data_dir)
await container.initialize({"api_key": "...", "model": "gpt-3.5-turbo"})
response = await container.chat("你好")
await container.cleanup()
```

### 自定义内核适配器（Rust）
```python
from cradle_selrena_core.ports import KernelPort

class RustKernelAdapter(KernelPort):
    async def send_message(self, text: str, emotion: str = None):
        # 实现与 Rust 内核的通信
        pass
```

## 下一步工作

### 短期（1-2 周）
- [ ] 完善错误处理和异常恢复
- [ ] 添加更多单元测试
- [ ] 实现向量记忆检索（Chroma/FAISS）
- [ ] 集成视觉理解模型（BLIP/LLaVA）

### 中期（1-2 月）
- [ ] 实现完整的 MCP Agent 支持
- [ ] 添加技能学习系统
- [ ] 优化情感演化模型
- [ ] 实现多用户会话管理

### 长期（3-6 月）
- [ ] Rust 内核实现
- [ ] 性能优化（批处理/缓存）
- [ ] 分布式部署支持
- [ ] 插件市场生态

## 验证清单

- ✅ 目录结构符合文档要求
- ✅ 所有层职责清晰，无越界
- ✅ 接口抽象完整，支持 TS/Rust 替换
- ✅ 最小可用代码实现（可对话）
- ✅ 类型注解完整
- ✅ 文档字符串完整
- ✅ 日志记录规范
- ✅ 异步编程规范

## 总结

本次重构严格按照架构文档要求，实现了：
1. **清晰的分层架构**：domain/application/ports/adapters/inference
2. **依赖倒置**：所有外部依赖通过 ports 层抽象
3. **接口抽象**：支持 TS→Rust 无缝替换
4. **最小可用**：可独立运行对话功能

重构后的代码：
- 更易维护（职责清晰）
- 更易测试（接口可 Mock）
- 更易扩展（插件化）
- 无技术债（符合最佳实践）

现在可以直接基于此架构进行开发，无需再调整结构。
