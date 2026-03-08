# Python AI 核心层开发指南

本部分覆盖 Python 包中的所有层级，从基础设施到推理引擎，应遵循项目的 DDD 分层结构。

## 1. 核心基础设施层（core）
说明此层代码负责支撑整个平台的运行环境，所有模块均通过生命周期管理注册。

### 主要组件
* `config_manager.py` – 负责从内核或本地加载配置并校验（Pydantic）。
* `event_bus_client.py` – 订阅/发布内核事件的轻量客户端。
* `ai_service.py` – 封装对 ConversationService/MemoryService 等调用，供 TS 内核使用。
* `main_service.py` – 在容器启动时创建并初始化各子服务。

### 开发要点
1. **生命周期**: 继承 `Lifecycle` 接口（`core/lifecycle.py`），在 `on_start`/`on_stop` 里启动/清理资源。
2. **异步与线程**: 所有 IO 操作均使用 `asyncio`，避免阻塞主事件循环。使用 `asyncio.to_thread` 封装 CPU 密集型任务。
3. **日志统一**: 使用 `core/logger.py` 提供的 `get_logger(__name__)`，避免在模块中直接创建 logger。
4. **配置**: 每个模块通过 `config_manager.get()` 获取其配置片段，并在启动时执行 Pydantic 验证。

```python
# config_manager example
from cradle_selrena_core.core.config_manager import global_config

class SomeService(Lifecycle):
    async def on_start(self):
        cfg = global_config.get_system().some_service
        # 类型已验证
        self.timeout = cfg.timeout
```

```python
# event_bus_client example
from cradle_selrena_core.core.event_bus_client import EventBusClient

bus = EventBusClient()
await bus.connect()
await bus.subscribe("user.input", self.handle_input)
```

---

## 2. 适配器层（adapters）
此层实现 ports 定义的接口，是与外部系统沟通的唯一窗口。

### 接口实现示例
* `KernelPort` – 发送消息/音频/读写文件等，由 TS/Rust 内核通过事件来调用。
* `MemoryPort` – 抽象存储，当前实现为文件系统，未来可扩展为数据库或向量库。

```python
from cradle_selrena_core.ports import KernelPort

class DummyKernelAdapter(KernelPort):
    async def send_message(self, text: str, emotion: str = None):
        print("[kernel]", text, emotion)
    # 其余方法实现省略
```

### 编写新适配器
1. 在 `adapters/` 新建模块，例如 `discord.py`。
2. 继承对应 port，并实现所有抽象方法。
3. 在 `container.py` 中注册适配器实例。
4. 撰写单元测试，使用 dummy bus 或直接调用方法。

**注意**: 业务逻辑应保留在 application/ 而非 adapter，否则跨语言替换时需重复修改。

---

## 3. 领域层（domain）
领域层包含不依赖外部的纯业务模型。

### 设计规范
* 使用 `@dataclass` 定义简单结构，静态类型注解。
* 若需验证或序列化，使用 Pydantic 模型（在 schemas/domain.py 定义并导入）。
* 模型之间通过组合而非继承关联。

```python
from dataclasses import dataclass

@dataclass
class Persona:
    name: str
    identity: str
    values: list[str]
```

### 扩展建议
1. 新增特性（例如 `background_story`）时，先在 dataclass 添加字段并赋默认值，随后更新对应的 Pydantic Schema。
2. 对于枚举类型使用 `enum.Enum` 并在 Schema 中引用。
3. 领域层应无任何业务逻辑，仅提供 getters/setters 或计算属性。

### 测试
领域模型的单元测试仅需构造实例并验证属性，可在 `tests/unit` 添加简单用例：
```python
def test_persona_layers():
    from cradle_selrena_core.domain.persona import Persona
    p = Persona(name="A", identity="I", values=["v"])
    assert p.name == "A"
```

---

## 4. 数据模型层（schemas）
Schemas 层负责所有外部数据结构的定义与验证。

### Pydantic 编写规范
* 每个模式放在对应文件，如 `events.py`, `payloads.py`。
* 使用 `Field` 提供描述和默认值。
* 复用类型，如 `ChatMessage = Dict[str, Any]`。

```python
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(..., description="user/assistant/system")
    content: str
```

### 映射关系
* 配置 YAML → `schemas/configs/*.py` 模型。
* 事件总线消息 → `schemas/events.py`。
* 外部 API 返回 → 自行定义并在适配器层使用。

### 文档与校验
在模型上添加 docstring、`@validator` 进行高级校验。

---

## 5. 应用服务层（application）
应用层编排领域模型、适配器和推理引擎实现具体业务用例。

### 常见流程
1. 接收输入（来自 AIService 或事件）。
2. 调用 `MemoryPort` 检索相关记忆。
3. 构建上下文（Persona + 历史 + 新消息）。
4. 通过 `InferencePort` 生成回复。
5. 更新记忆和情绪状态。
6. 通过 `KernelPort` 发送输出。

```python
# ConversationService.process_message
async def process_message(self, user_input, is_external=False):
    relevant = await self.memory.retrieve_memories(user_input)
    context = build_context(...)
    response = await self.llm.generate(context)
    await self.memory.save_memory(Memory(...))
    await self.kernel.send_message(response)
    return response
```

### 扩展指南
- 添加新功能时不应修改已有方法，可扩展为钩子或事件订阅。
- 使用依赖注入获取 ports 实例，避免静态引用。
- 业务逻辑复杂时可拆分为多个服务，例如将推理逻辑提取到 `ReasoningService`。

---

## 6. 工具层（utils）
工具库提供全局通用功能，禁止包含业务状态或副作用。

### 设计原则
* 纯函数：输入决定输出，无任何全局状态。
* 无外界依赖：避免 `import` 非标准库模块。
* 易于测试：每个工具都有独立单元测试。

### 常见模块
- `async_utils.py`：包装 `asyncio` 任务、超时处理。
- `path.py`：统一使用 `pathlib.Path`，提供项目根路径常量。
- `logger.py`：统一日志配置（默认输出到 stdout 并发送给内核）。
- `yaml_io.py`：简化 YAML 读写并自动转换为 Pydantic 对象。

```python
def load_yaml(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)
```

### 目录示例
```
utils/
├── async_utils.py
├── config.py
├── exceptions.py
├── logger.py
├── path.py
└── yaml_io.py
```

---

## 7. 业务核心层（persona/memory/intention/agent）
此层承担大多数 AI 相关逻辑，必须保持纯粹、可测试。

### 拆分策略
* 按功能模块拆分目录（已见示例结构）。
* 每个模块仅暴露必要 API，内部使用私有辅助函数。
* 参数传递而非全局访问，以便单元测试模拟不同场景。

### 特殊注意
- **persona**: 统一构建系统提示词、身份属性、情感更新；避免引入任何 I/O。
- **memory**: 提供存/检/忘 API，内部可调用 `MemoryPort`；不直接读写文件。
- **intention**: 向外暴露 `parse_intent()`、`plan_task()` 等纯函数。
- **agent**: 仅负责生成 MCP 指令，执行由内核完成。

```python
# memory/episodic.py
class EpisodicMemory:
    def __init__(self, store: MemoryPort):
        self._store = store

    async def add_event(self, text: str):
        await self._store.save_memory(Memory(content=text))
```

### 命名规则
- 模块/类使用小写下划线和驼峰命名，如 `task_planner.py` / `TaskPlanner`。
- 变量使用小写带下划线，常量大写。 

---

## 8. 推理引擎层（inference）
该层封装所有与 LLM、视觉、语音等推理相关的逻辑。

### 引擎接口
* `BaseBrainBackend` 定义基本方法 `async def generate(self, messages)`。
* 所有引擎实现必须是无状态的可重入对象。

```python
class DummyEngine(BaseBrainBackend):
    async def generate(self, messages):
        return "(dummy)"
```

### 添加新引擎
1. 在 `inference/engines/` 下创建子模块（`myengine.py`）。
2. 继承 `BaseBrainBackend` 并实现 `initialize`, `generate`, 可选 `perceive`。
3. 在 `env` 或配置中注册引擎名称。
4. 编写单元测试模拟输入->输出流程。

### 调度器 & 路由
* `scheduler/router.py` 根据负载与策略选择引擎实例。
* `inference/engines/router.py` 可实现视觉/文本混路逻辑。
* 路由应保持纯逻辑，负载信息通过参数传入。

```python
class EngineRouter:
    async def choose(self, is_visual: bool) -> BaseBrainBackend:
        if is_visual:
            return await self._load_engine('vision')
        return await self._load_engine('default')
```

### 性能注意
- 尽量使用单例/池化避免重复初始化大模型。
- 长时间运行的引擎应支持 `cleanup()`。

---

> **此文档为模板**，后续根据项目需求逐层补充示例和注意事项。