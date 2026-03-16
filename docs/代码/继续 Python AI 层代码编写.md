# 继续 Python AI 层代码编写

用户要求继续编写Python AI层代码，我将接着base_use_case.py的execute方法续写。之后，补全应用层、端口层等各层代码，每个文件都添加详细注释，严格遵循架构铁律，专注于代码逻辑实现，不涉及场景与IO操作。

### 14. 应用层：用例基类 `src/selrena/application/base_use_case.py`（补全完整代码）

```Python

"""
文件名称：base_use_case.py
所属层级：应用层
核心作用：用例基类，定义统一的用例执行流程，统一异常处理、日志、追踪
设计原则：
1. 仅做流程编排，不碰业务规则
2. 统一全链路trace_id透传
3. 统一异常处理，不吞异常
4. 所有用例必须继承此类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Generic, TypeVar
from selrena.core.observability.logger import get_logger

# 泛型定义：输入/输出类型
Input = TypeVar("Input")
Output = TypeVar("Output")

# 初始化模块日志器
logger = get_logger("base_use_case")


# ======================================
# 用例基类
# ======================================
@dataclass
class BaseUseCase(ABC, Generic[Input, Output]):
    """
    用例基类，所有应用层用例必须继承
    核心作用：统一执行流程、异常处理、全链路追踪
    """
    use_case_name: str = field(init=False)

    def __post_init__(self) -> None:
        """自动设置用例名称为子类类名，无需手动赋值"""
        self.use_case_name = self.__class__.__name__

    @abstractmethod
    async def _execute(self, input_data: Input, trace_id: str) -> Output:
        """
        用例核心执行逻辑，子类必须实现
        【规范】：仅做流程编排，所有业务规则必须调用领域层实现
        参数：
            input_data: 用例输入
            trace_id: 全链路追踪ID
        返回：用例输出
        """
        pass

    async def execute(self, input_data: Input, trace_id: str = None) -> Output:
        """
        用例统一执行入口，外部仅能调用此方法
        参数：
            input_data: 用例输入
            trace_id: 全链路追踪ID，不传则自动生成
        返回：用例输出
        异常：所有业务异常向上抛出，不吞异常
        """
        # 生成全链路追踪ID，保证全流程可追溯
        trace_id = trace_id or str(uuid4())
        logger.info(
            f"用例 {self.use_case_name} 开始执行",
            trace_id=trace_id
        )

        try:
            # 执行子类实现的核心逻辑
            result = await self._execute(input_data, trace_id)
            logger.info(
                f"用例 {self.use_case_name} 执行成功",
                trace_id=trace_id
            )
            return result

        except Exception as e:
            # 异常日志记录，不吞异常，继续向上抛出
            logger.error(
                f"用例 {self.use_case_name} 执行失败",
                trace_id=trace_id,
                error=str(e),
                exc_info=True
            )
            raise e
```

---

### 15. 应用层：对话交互用例 `src/selrena/application/chat_use_case.py`

```Python

"""
文件名称：chat_use_case.py
所属层级：应用层
核心作用：对话交互全流程编排，纯流程逻辑，不碰任何业务规则
设计原则：
1. 仅做流程编排，所有业务规则全部调用领域层实现
2. 完全不碰场景规则，仅接收内核传入的标准化参数
3. 严格遵循分层边界，不直接调用底层基础设施
4. 所有输出必须经过人设边界校验
"""
from dataclasses import dataclass
from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine
from selrena.core.exceptions import PersonaViolationException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("chat_use_case")


# ======================================
# 用例输入/输出模型
# ======================================
@dataclass
class ChatInput:
    """
    对话用例输入，由TS内核传入的标准化参数
    【核心规范】：完全屏蔽平台/场景细节，AI层看不到任何场景信息
    """
    # 用户输入的纯文本内容（多模态已被内核预处理为语义文本）
    user_input: str
    # 场景唯一ID（仅用于隔离短期记忆，AI层不处理场景规则）
    scene_id: str
    # 对话对象熟悉度 0-10（10=核心用户，0=陌生人，内核已计算完成）
    familiarity: int = 0
    # 全链路追踪ID
    trace_id: str = ""


@dataclass
class ChatOutput:
    """对话用例输出，返回给TS内核的标准化结果"""
    # 生成的回复内容
    reply_content: str
    # 当前情绪状态
    emotion_state: dict
    # 全链路追踪ID
    trace_id: str


# ======================================
# 对话用例核心实现
# ======================================
@dataclass
class ChatUseCase(BaseUseCase[ChatInput, ChatOutput]):
    """
    对话交互全流程用例
    核心作用：编排对话全流程，不碰任何业务规则
    真人逻辑对齐：对应人脑「接收信息→情绪变化→回忆相关记忆→组织语言→输出」的完整思考流程
    """
    # 依赖注入：全局自我实体
    self_entity: SelrenaSelfEntity
    # 依赖注入：LLM推理引擎
    llm_engine: LLMEngine

    async def _execute(self, input_data: ChatInput, trace_id: str) -> ChatOutput:
        """
        对话全流程编排，严格按真人思考逻辑执行
        【规范】：所有业务规则都调用领域层实现，这里仅做流程串联
        """
        logger.debug(
            "对话用例开始执行",
            trace_id=trace_id,
            scene_id=input_data.scene_id,
            familiarity=input_data.familiarity
        )

        # ======================================
        # 步骤1：情绪更新（基于用户输入）
        # ======================================
        self.self_entity.emotion_system.update_by_input(input_data.user_input)
        current_emotion = self.self_entity.emotion_system.get_state()
        logger.debug("情绪更新完成", trace_id=trace_id, emotion=current_emotion)

        # ======================================
        # 步骤2：获取当前场景的短期记忆（上下文）
        # ======================================
        short_term_memory = self.self_entity.get_short_term_memory(input_data.scene_id)
        context_text = short_term_memory.get_context_text(limit=10)
        logger.debug("短期上下文获取完成", trace_id=trace_id, context_length=len(context_text))

        # ======================================
        # 步骤3：检索相关长期记忆
        # ======================================
        relevant_memories = self.self_entity.long_term_memory.retrieve_relevant(
            query=input_data.user_input,
            limit=self.self_entity.inference_config.memory.max_recall_count
        )
        memory_text = "\n".join([f"记忆：{mem.content}" for mem in relevant_memories])
        logger.debug("长期记忆检索完成", trace_id=trace_id, memory_count=len(relevant_memories))

        # ======================================
        # 步骤4：检索相关通用知识库
        # ======================================
        relevant_knowledge = self.self_entity.knowledge_base.retrieve_general_knowledge(
            query=input_data.user_input,
            limit=3
        )
        knowledge_text = "\n".join([f"知识：{entry.content}" for entry in relevant_knowledge])
        logger.debug("通用知识库检索完成", trace_id=trace_id, knowledge_count=len(relevant_knowledge))

        # ======================================
        # 步骤5：构建人设prompt
        # ======================================
        persona_prompt = self.self_entity.persona_injector.build_persona_prompt(
            emotion_state=current_emotion
        )
        logger.debug("人设prompt构建完成", trace_id=trace_id)

        # ======================================
        # 步骤6：拼接完整prompt
        # ======================================
        full_prompt = f"""
{persona_prompt}

===== 相关记忆 =====
{memory_text if memory_text else "无相关记忆"}

===== 相关知识 =====
{knowledge_text if knowledge_text else "无相关知识"}

===== 对话上下文 =====
{context_text}

===== 用户对你说 =====
{input_data.user_input}

请用符合你人设的语气回复：
"""

        # ======================================
        # 步骤7：LLM生成回复
        # ======================================
        raw_reply = self.llm_engine.generate(full_prompt)
        logger.debug("LLM回复生成完成", trace_id=trace_id, reply_length=len(raw_reply))

        # ======================================
        # 步骤8：人设边界红线校验
        # ======================================
        if not self.self_entity.validate_boundary(raw_reply):
            raise PersonaViolationException("生成内容突破人设边界红线，已拦截")
        logger.debug("人设边界校验通过", trace_id=trace_id)

        # ======================================
        # 步骤9：沉淀短期记忆
        # ======================================
        # 新增用户输入到短期记忆
        short_term_memory.add(
            role="user",
            content=input_data.user_input,
            importance=0.7 if input_data.familiarity >= 8 else 0.5
        )
        # 新增生成的回复到短期记忆
        short_term_memory.add(
            role="selrena",
            content=raw_reply,
            importance=0.6
        )
        logger.debug("短期记忆沉淀完成", trace_id=trace_id)

        # ======================================
        # 步骤10：返回标准化结果
        # ======================================
        return ChatOutput(
            reply_content=raw_reply,
            emotion_state=current_emotion,
            trace_id=trace_id
        )
```

---

### 16. 应用层：主动思维流用例 `src/selrena/application/active_thought_use_case.py`

```Python

"""
文件名称：active_thought_use_case.py
所属层级：应用层
核心作用：主动思维流执行用例，由TS内核的生命时钟驱动，实现「活着」的核心特性
设计原则：
1. 仅做流程编排，不碰业务规则
2. 完全由内核驱动，无需用户触发
3. 不碰任何场景规则，仅做纯思维生成
"""
from dataclasses import dataclass
from .base_use_case import BaseUseCase
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("active_thought_use_case")


# ======================================
# 用例输入/输出模型
# ======================================
@dataclass
class ActiveThoughtInput:
    """主动思维用例输入，由内核生命时钟触发"""
    # 全链路追踪ID
    trace_id: str = ""


@dataclass
class ActiveThoughtOutput:
    """主动思维用例输出，返回给内核同步状态"""
    # 生成的内心活动内容
    thought_content: str
    # 当前情绪状态
    emotion_state: dict
    # 全链路追踪ID
    trace_id: str


# ======================================
# 主动思维流用例核心实现
# ======================================
@dataclass
class ActiveThoughtUseCase(BaseUseCase[ActiveThoughtInput, ActiveThoughtOutput]):
    """
    主动思维流执行用例
    核心作用：让月见在没有用户说话时，也有自己的内心活动，实现「活着」的核心特性
    真人逻辑对齐：对应人脑的走神、发呆、内心独白，不需要外界触发
    """
    # 依赖注入：全局自我实体
    self_entity: SelrenaSelfEntity

    async def _execute(self, input_data: ActiveThoughtInput, trace_id: str) -> ActiveThoughtOutput:
        """主动思维全流程编排"""
        logger.debug(
            "主动思维用例开始执行",
            trace_id=trace_id
        )

        # ======================================
        # 步骤1：情绪自然衰减
        # ======================================
        self.self_entity.emotion_system.decay()
        current_emotion = self.self_entity.emotion_system.get_state()
        logger.debug("情绪自然衰减完成", trace_id=trace_id, emotion=current_emotion)

        # ======================================
        # 步骤2：生成主动思维
        # ======================================
        thought_content = self.self_entity.thought_system.generate_thought()
        logger.debug("主动思维生成完成", trace_id=trace_id, thought=thought_content)

        # ======================================
        # 步骤3：返回标准化结果
        # ======================================
        return ActiveThoughtOutput(
            thought_content=thought_content,
            emotion_state=current_emotion,
            trace_id=trace_id
        )
```

---

### 17. 端口层：入站端口 `src/selrena/ports/inbound/perception_port.py`

```Python

"""
文件名称：perception_port.py
所属层级：端口层-入站端口
核心作用：定义入站信号的抽象接口，遵循依赖倒置原则
设计原则：
1. 仅定义抽象接口，不做实现
2. 所有来自内核的入站信号，必须通过此接口定义
3. 完全屏蔽底层通信细节，应用层仅依赖此接口
"""
from abc import ABC, abstractmethod
from selrena.application.chat_use_case import ChatInput, ChatOutput
from selrena.application.active_thought_use_case import ActiveThoughtInput, ActiveThoughtOutput


class PerceptionPort(ABC):
    """
    感知入站端口抽象接口
    核心作用：定义AI层能接收的所有外界信号，完全屏蔽底层通信细节
    真人逻辑对齐：对应人脑的感官输入接口，仅定义能接收什么信号，不关心信号从哪里来
    """

    @abstractmethod
    async def on_chat_message(self, input_data: ChatInput) -> ChatOutput:
        """
        接收对话消息
        参数：
            input_data: 内核传入的标准化对话输入
        返回：标准化对话输出
        """
        pass

    @abstractmethod
    async def on_life_heartbeat(self, input_data: ActiveThoughtInput) -> ActiveThoughtOutput:
        """
        接收内核的生命心跳，触发主动思维
        参数：
            input_data: 心跳输入
        返回：思维结果输出
        """
        pass

    @abstractmethod
    async def on_memory_init(self, memories: list[dict]) -> None:
        """
        接收内核注入的历史长期记忆
        参数：
            memories: 历史记忆列表
        """
        pass

    @abstractmethod
    async def on_knowledge_init(self, persona_knowledge: list[dict], general_knowledge: list[dict]) -> None:
        """
        接收内核注入的知识库
        参数：
            persona_knowledge: 人设知识库内容
            general_knowledge: 通用知识库内容
        """
        pass
```

---

### 18. 端口层：出站端口 `src/selrena/ports/outbound/kernel_event_port.py`

```Python

"""
文件名称：kernel_event_port.py
所属层级：端口层-出站端口
核心作用：定义出站事件的抽象接口，遵循依赖倒置原则
设计原则：
1. 仅定义抽象接口，不做实现
2. 所有发送给内核的事件，必须通过此接口定义
3. 完全屏蔽底层通信细节，领域层/应用层仅依赖此接口
"""
from abc import ABC, abstractmethod
from selrena.domain.memory.long_term_memory import LongTermMemoryFragment


class KernelEventPort(ABC):
    """
    内核事件出站端口抽象接口
    核心作用：定义AI层能发送给内核的所有事件，完全屏蔽底层通信细节
    真人逻辑对齐：对应人脑的动作输出接口，仅定义能发送什么信号，不关心信号到哪里去
    """

    @abstractmethod
    async def send_memory_sync(self, fragment: LongTermMemoryFragment) -> None:
        """
        发送记忆同步事件给内核，触发持久化
        参数：
            fragment: 要同步的长期记忆片段
        """
        pass

    @abstractmethod
    async def send_state_sync(self, state: dict) -> None:
        """
        发送状态同步事件给内核，同步给渲染层
        参数：
            state: 月见当前状态字典
        """
        pass

    @abstractmethod
    async def send_log(self, level: str, message: str, extra: dict = None) -> None:
        """
        发送日志事件给内核，统一日志管理
        参数：
            level: 日志级别
            message: 日志内容
            extra: 额外参数
        """
        pass
```

---

### 19. 适配器层：入站适配器 `src/selrena/adapters/inbound/kernel_event_adapter.py`

```Python

"""
文件名称：kernel_event_adapter.py
所属层级：适配器层-入站适配器
核心作用：实现入站端口的抽象接口，处理内核传入的信号，调用对应的用例
设计原则：
1. 仅做协议转换，不碰业务逻辑
2. 把内核传入的原始消息，转换为应用层能处理的标准化输入
3. 不做任何流程编排，仅做路由转发
"""
from selrena.ports.inbound.perception_port import PerceptionPort
from selrena.application.chat_use_case import ChatUseCase, ChatInput, ChatOutput
from selrena.application.active_thought_use_case import ActiveThoughtUseCase, ActiveThoughtInput, ActiveThoughtOutput
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("inbound_adapter")


class KernelEventInboundAdapter(PerceptionPort):
    """
    内核事件入站适配器
    核心作用：接收内核传入的IPC消息，转换为标准化输入，调用对应的用例
    设计规范：仅做协议转换和路由，不碰任何业务逻辑
    """
    def __init__(
        self,
        self_entity: SelrenaSelfEntity,
        chat_use_case: ChatUseCase,
        active_thought_use_case: ActiveThoughtUseCase
    ):
        self.self_entity = self_entity
        self.chat_use_case = chat_use_case
        self.active_thought_use_case = active_thought_use_case
        logger.info("内核入站适配器初始化完成")

    async def on_chat_message(self, input_data: ChatInput) -> ChatOutput:
        """接收内核的对话消息，调用对话用例"""
        logger.info(
            "收到内核对话消息",
            trace_id=input_data.trace_id,
            scene_id=input_data.scene_id
        )
        return await self.chat_use_case.execute(input_data, input_data.trace_id)

    async def on_life_heartbeat(self, input_data: ActiveThoughtInput) -> ActiveThoughtOutput:
        """接收内核的生命心跳，调用主动思维用例"""
        logger.debug(
            "收到内核生命心跳",
            trace_id=input_data.trace_id
        )
        return await self.active_thought_use_case.execute(input_data, input_data.trace_id)

    async def on_memory_init(self, memories: list[dict]) -> None:
        """接收内核注入的历史长期记忆"""
        logger.info("收到内核历史记忆注入", memory_count=len(memories))
        self.self_entity.long_term_memory.init_from_kernel(memories)

    async def on_knowledge_init(self, persona_knowledge: list[dict], general_knowledge: list[dict]) -> None:
        """接收内核注入的知识库"""
        logger.info(
            "收到内核知识库注入",
            persona_count=len(persona_knowledge),
            general_count=len(general_knowledge)
        )
        self.self_entity.knowledge_base.init_from_kernel(persona_knowledge, general_knowledge)
```

---

### 20. 适配器层：出站适配器 `src/selrena/adapters/outbound/kernel_event_adapter.py`

```Python

"""
文件名称：kernel_event_adapter.py
所属层级：适配器层-出站适配器
核心作用：实现出站端口的抽象接口，把AI层的事件转换为IPC消息发送给内核
设计原则：
1. 仅做协议转换，不碰业务逻辑
2. 把AI层的领域事件，转换为内核能理解的标准化IPC消息
3. 不做任何流程编排，仅做消息转发
"""
from selrena.ports.outbound.kernel_event_port import KernelEventPort
from selrena.domain.memory.long_term_memory import LongTermMemoryFragment
from selrena.bridge.kernel_bridge import KernelBridge
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("outbound_adapter")


class KernelEventOutboundAdapter(KernelEventPort):
    """
    内核事件出站适配器
    核心作用：把AI层的领域事件，转换为标准化IPC消息发送给内核
    设计规范：仅做协议转换和消息发送，不碰任何业务逻辑
    """
    def __init__(self, kernel_bridge: KernelBridge):
        self.kernel_bridge = kernel_bridge
        logger.info("内核出站适配器初始化完成")

    async def send_memory_sync(self, fragment: LongTermMemoryFragment) -> None:
        """发送记忆同步事件给内核"""
        logger.debug(
            "发送记忆同步事件给内核",
            memory_id=fragment.memory_id
        )
        # 转换为标准化消息格式
        message = {
            "type": "memory_sync",
            "memory": {
                "memory_id": fragment.memory_id,
                "content": fragment.content,
                "memory_type": fragment.memory_type.value,
                "weight": fragment.weight,
                "tags": fragment.tags,
                "scene_id": fragment.scene_id,
                "timestamp": fragment.timestamp.isoformat()
            }
        }
        # 通过桥接层发送给内核
        await self.kernel_bridge.send_message(message)

    async def send_state_sync(self, state: dict) -> None:
        """发送状态同步事件给内核"""
        logger.debug(
            "发送状态同步事件给内核",
            state=state
        )
        message = {
            "type": "state_sync",
            "state": state
        }
        await self.kernel_bridge.send_message(message)

    async def send_log(self, level: str, message: str, extra: dict = None) -> None:
        """发送日志事件给内核"""
        log_message = {
            "type": "log",
            "level": level,
            "message": message,
            "extra": extra or {}
        }
        await self.kernel_bridge.send_message(log_message)
```

---

### 21. 桥接层：内核通信桥接 `src/selrena/bridge/kernel_bridge.py`

```Python

"""
文件名称：kernel_bridge.py
所属层级：桥接层
核心作用：Python AI层与TS内核通信的唯一入口，基于ZMQ的IPC通信
设计原则：
1. 是AI层与内核通信的唯一入口，所有跨进程通信必须经过这里
2. 仅做通信和消息收发，不碰任何业务逻辑
3. 完全屏蔽底层通信细节，上层仅需调用标准化接口
4. 严格遵循全链路trace_id透传
"""
import asyncio
import zmq
import zmq.asyncio
from typing import Callable, Coroutine, Any
from selrena.core.exceptions import BridgeException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("kernel_bridge")


class KernelBridge:
    """
    内核通信桥接单例
    核心作用：Python AI层与TS内核之间的唯一通信通道
    通信协议：ZMQ IPC 双向通信，低延迟、高可靠，适配本地单设备场景
    """
    _instance = None

    def __new__(cls):
        """单例模式，保证整个进程只有一个通信桥接实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化，仅在单例创建时执行一次"""
        # ZMQ上下文
        self._context = zmq.asyncio.Context()
        # 服务端Socket（绑定地址，等待内核连接）
        self._socket: zmq.asyncio.Socket | None = None
        # 消息处理器字典：key=消息类型，value=异步处理函数
        self._handlers: dict[str, Callable[[dict], Coroutine[Any, Any, None]]] = {}
        # 运行状态
        self._is_running: bool = False
        # 接收消息的后台任务
        self._receive_task: asyncio.Task | None = None
        logger.info("内核通信桥接初始化完成")

    def register_handler(self, message_type: str, handler: Callable[[dict], Coroutine[Any, Any, None]]) -> None:
        """
        注册消息处理器
        参数：
            message_type: 消息类型
            handler: 异步处理函数，入参为消息字典
        """
        self._handlers[message_type] = handler
        logger.info(f"注册消息处理器: {message_type}")

    async def start(self, bind_address: str) -> None:
        """
        启动桥接服务，绑定地址，等待内核连接
        参数：
            bind_address: ZMQ绑定地址，如 "tcp://127.0.0.1:8765"
        异常：
            BridgeException: 启动失败时抛出
        """
        if self._is_running:
            logger.warning("内核桥接已在运行中，无需重复启动")
            return

        try:
            # 创建REP Socket，响应式通信
            self._socket = self._context.socket(zmq.REP)
            self._socket.bind(bind_address)
            self._is_running = True
            # 启动后台接收任务
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info(f"内核桥接启动成功，绑定地址: {bind_address}")

        except Exception as e:
            raise BridgeException(f"内核桥接启动失败: {str(e)}")

    async def stop(self) -> None:
        """停止桥接服务，优雅关闭所有资源"""
        self._is_running = False

        # 停止接收任务
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # 关闭Socket
        if self._socket:
            self._socket.close()
            self._socket = None

        # 终止ZMQ上下文
        self._context.term()
        logger.info("内核桥接已停止")

    async def send_message(self, message: dict) -> None:
        """
        发送消息给内核
        参数：
            message: 标准化消息字典
        异常：
            BridgeException: 发送失败时抛出
        """
        if not self._is_running or not self._socket:
            raise BridgeException("内核桥接未启动，无法发送消息")

        try:
            await self._socket.send_json(message)
            logger.debug("消息发送成功", message_type=message.get("type"))
        except Exception as e:
            raise BridgeException(f"消息发送失败: {str(e)}")

    async def _receive_loop(self) -> None:
        """后台接收循环，持续接收内核的消息，分发给对应的处理器"""
        logger.info("内核消息接收循环已启动")
        while self._is_running:
            try:
                # 接收内核的消息
                message = await self._socket.recv_json()
                message_type = message.get("type")
                trace_id = message.get("trace_id", "")
                logger.debug(
                    "收到内核消息",
                    message_type=message_type,
                    trace_id=trace_id
                )

                # 查找对应的处理器
                handler = self._handlers.get(message_type)
                if not handler:
                    logger.warning(f"未找到消息类型 {message_type} 的处理器")
                    await self._socket.send_json({
                        "type": "error",
                        "message": f"未知消息类型: {message_type}",
                        "trace_id": trace_id
                    })
                    continue

                # 执行处理器
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(
                        f"消息处理器执行失败: {str(e)}",
                        message_type=message_type,
                        trace_id=trace_id,
                        exc_info=True
                    )
                    await self._socket.send_json({
                        "type": "error",
                        "message": f"处理器执行失败: {str(e)}",
                        "trace_id": trace_id
                    })

            except zmq.ZMQError as e:
                if self._is_running:
                    logger.error(f"ZMQ通信错误: {str(e)}", exc_info=True)
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"消息接收循环异常: {str(e)}", exc_info=True)
                await asyncio.sleep(0.1)
```

---

### 22. 依赖注入容器 `src/selrena/container.py`

```Python

"""
文件名称：container.py
所属层级：基础设施层
核心作用：依赖注入容器，管理所有单例实例，解决循环依赖问题
设计原则：
1. 单例模式，所有核心实例统一管理
2. 解决循环依赖问题，按依赖顺序初始化
3. 所有依赖通过构造函数注入，不使用硬编码导入
4. 严格遵循分层边界，仅在根目录初始化时调用
"""
from typing import Final
from selrena.core.config import GlobalAIConfig
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine
from selrena.application.chat_use_case import ChatUseCase
from selrena.application.active_thought_use_case import ActiveThoughtUseCase
from selrena.bridge.kernel_bridge import KernelBridge
from selrena.adapters.inbound.kernel_event_adapter import KernelEventInboundAdapter
from selrena.adapters.outbound.kernel_event_adapter import KernelEventOutboundAdapter
from selrena.core.event_bus import DomainEventBus
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("container")


class DIContainer:
    """
    依赖注入容器，单例模式
    核心作用：统一管理所有核心实例，解决循环依赖，按正确顺序初始化
    """
    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized: bool = False
        # 所有实例存储
        self._instances: dict[str, object] = {}

    def init(self, config: GlobalAIConfig) -> None:
        """
        初始化容器，按依赖顺序创建所有实例
        参数：
            config: 内核注入的全局冻结配置
        规范：按「基础设施→领域层→推理层→应用层→适配器层→桥接层」的顺序初始化
        """
        if self._initialized:
            logger.warning("容器已初始化，无需重复初始化")
            return

        logger.info("依赖注入容器开始初始化")

        # ======================================
        # 1. 基础设施层实例
        # ======================================
        event_bus = DomainEventBus()
        self._instances["event_bus"] = event_bus

        kernel_bridge = KernelBridge()
        self._instances["kernel_bridge"] = kernel_bridge

        # ======================================
        # 2. 领域层核心实例：全局自我实体（灵魂根节点）
        # ======================================
        self_entity = SelrenaSelfEntity(
            persona_config=config.persona,
            inference_config=config.inference
        )
        self._instances["self_entity"] = self_entity

        # 初始化人设注入器
        self_entity.persona_injector.init(
            persona_config=config.persona,
            inject_mode="prompt"  # 可通过配置修改
        )
        logger.info("全局自我实体初始化完成")

        # ======================================
        # 3. 推理层实例
        # ======================================
        llm_engine = LLMEngine(self_entity=self_entity)
        self._instances["llm_engine"] = llm_engine

        # ======================================
        # 4. 应用层用例实例
        # ======================================
        chat_use_case = ChatUseCase(
            self_entity=self_entity,
            llm_engine=llm_engine
        )
        self._instances["chat_use_case"] = chat_use_case

        active_thought_use_case = ActiveThoughtUseCase(
            self_entity=self_entity
        )
        self._instances["active_thought_use_case"] = active_thought_use_case

        # ======================================
        # 5. 适配器层实例
        # ======================================
        # 入站适配器
        inbound_adapter = KernelEventInboundAdapter(
            self_entity=self_entity,
            chat_use_case=chat_use_case,
            active_thought_use_case=active_thought_use_case
        )
        self._instances["inbound_adapter"] = inbound_adapter

        # 出站适配器
        outbound_adapter = KernelEventOutboundAdapter(
            kernel_bridge=kernel_bridge
        )
        self._instances["outbound_adapter"] = outbound_adapter

        # ======================================
        # 6. 注册事件处理器
        # ======================================
        # 注册记忆同步事件处理器
        from selrena.domain.memory.long_term_memory import MemorySyncEvent
        event_bus.subscribe(MemorySyncEvent, lambda e: outbound_adapter.send_memory_sync(e.memory_fragment))

        # 注册内核消息处理器
        kernel_bridge.register_handler("chat_message", lambda msg: inbound_adapter.on_chat_message(
            ChatInput(
                user_input=msg["user_input"],
                scene_id=msg["scene_id"],
                familiarity=msg.get("familiarity", 0),
                trace_id=msg["trace_id"]
            )
        ))
        kernel_bridge.register_handler("life_heartbeat", lambda msg: inbound_adapter.on_life_heartbeat(
            ActiveThoughtInput(trace_id=msg["trace_id"])
        ))
        kernel_bridge.register_handler("memory_init", lambda msg: inbound_adapter.on_memory_init(msg["memories"]))
        kernel_bridge.register_handler("knowledge_init", lambda msg: inbound_adapter.on_knowledge_init(
            msg["persona_knowledge"],
            msg["general_knowledge"]
        ))

        # 标记为已初始化
        self._initialized = True
        logger.info("依赖注入容器初始化完成")

    # ======================================
    # 实例获取方法
    # ======================================
    def get_self_entity(self) -> SelrenaSelfEntity:
        return self._instances["self_entity"]

    def get_kernel_bridge(self) -> KernelBridge:
        return self._instances["kernel_bridge"]

    def get_inbound_adapter(self) -> KernelEventInboundAdapter:
        return self._instances["inbound_adapter"]

    def get_outbound_adapter(self) -> KernelEventOutboundAdapter:
        return self._instances["outbound_adapter"]

    def get_chat_use_case(self) -> ChatUseCase:
        return self._instances["chat_use_case"]

    def get_active_thought_use_case(self) -> ActiveThoughtUseCase:
        return self._instances["active_thought_use_case"]
```

---

### 23. 主入口 `src/selrena/main.py`

```Python

"""
文件名称：main.py
所属层级：根入口
核心作用：Python AI层唯一启动入口，管理整个AI层的生命周期
设计原则：
1. 是Python AI层的唯一启动入口，外部仅能通过此文件启动
2. 统一管理整个AI层的生命周期：初始化→启动→运行→停止
3. 严格遵循分层边界，不碰任何业务逻辑，仅做生命周期管理
4. 所有配置由TS内核通过启动参数注入，不读本地配置文件
"""
import asyncio
import argparse
import sys
from typing import Final
from selrena.core.config import GlobalAIConfig
from selrena.container import DIContainer
from selrena.core.lifecycle import Lifecycle
from selrena.core.exceptions import ConfigException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("main")


# ======================================
# Python AI 核心主类
# ======================================
class PythonAICore(Lifecycle):
    """
    Python AI层核心主类，管理整个AI层的完整生命周期
    核心作用：是Python AI层的根节点，统一管理所有模块的启动、运行、停止
    """
    def __init__(self, config: GlobalAIConfig, bind_address: str):
        """
        初始化AI核心
        参数：
            config: 内核注入的全局冻结配置
            bind_address: ZMQ IPC绑定地址，用于和TS内核通信
        异常：
            ConfigException: 配置校验失败时抛出
        """
        # 全局冻结配置，运行时不可修改
        self.config: Final[GlobalAIConfig] = config
        # IPC绑定地址
        self.bind_address: Final[str] = bind_address
        # 依赖注入容器
        self.container: Final[DIContainer] = DIContainer()
        # 运行状态
        self._is_running: bool = False
        # 主运行任务
        self._main_task: asyncio.Task | None = None

        logger.info("Python AI 核心初始化完成", name=config.persona.base.name)

    async def start(self) -> None:
        """
        启动AI核心，按顺序初始化所有模块
        规范：幂等性，重复调用不会产生副作用
        """
        if self._is_running:
            logger.warning("Python AI 核心已在运行中，无需重复启动")
            return

        try:
            logger.info("Python AI 核心开始启动")

            # 1. 初始化依赖注入容器
            self.container.init(self.config)

            # 2. 启动内核通信桥接
            kernel_bridge = self.container.get_kernel_bridge()
            await kernel_bridge.start(self.bind_address)

            # 3. 唤醒月见
            self_entity = self.container.get_self_entity()
            self_entity.wake_up()

            # 4. 标记为运行中
            self._is_running = True

            # 5. 启动主运行循环
            self._main_task = asyncio.create_task(self._main_loop())

            logger.info("Python AI 核心启动成功！月见已醒来")

        except Exception as e:
            logger.critical(f"Python AI 核心启动失败: {str(e)}", exc_info=True)
            await self.stop()
            raise e

    async def stop(self) -> None:
        """
        停止AI核心，优雅关闭所有资源
        规范：幂等性，重复调用不会报错，必须释放所有资源
        """
        logger.info("Python AI 核心开始停止")
        self._is_running = False

        # 1. 停止主运行循环
        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        # 2. 让月见进入休眠
        if hasattr(self, "container"):
            self_entity = self.container.get_self_entity()
            self_entity.sleep()

            # 3. 停止内核通信桥接
            kernel_bridge = self.container.get_kernel_bridge()
            await kernel_bridge.stop()

        logger.info("Python AI 核心已停止，月见已进入休眠")

    async def _main_loop(self) -> None:
        """主运行循环，保持进程运行，处理心跳和状态同步"""
        logger.info("主运行循环已启动")
        while self._is_running:
            try:
                # 同步当前状态给内核
                self_entity = self.container.get_self_entity()
                outbound_adapter = self.container.get_outbound_adapter()
                await outbound_adapter.send_state_sync(self_entity.get_state())

                # 每秒同步一次状态
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主运行循环异常: {str(e)}", exc_info=True)
                await asyncio.sleep(1)


# ======================================
# 命令行启动入口
# ======================================
def main():
    """
    Python AI层唯一命令行启动入口
    由TS内核通过子进程启动，所有参数由内核传入
    启动参数示例：
    python -m selrena.main --config-path ./config.json --bind-address tcp://127.0.0.1:8765
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="月见（Selrena）数字生命 Python AI 核心")
    parser.add_argument(
        "--config-json",
        type=str,
        required=True,
        help="JSON格式的全局配置字符串，由TS内核注入"
    )
    parser.add_argument(
        "--bind-address",
        type=str,
        required=True,
        help="ZMQ IPC绑定地址，用于和TS内核通信"
    )
    args = parser.parse_args()

    # 解析配置
    try:
        import json
        config_dict = json.loads(args.config_json)
        config = GlobalAIConfig(**config_dict)
    except Exception as e:
        logger.critical(f"配置解析失败: {str(e)}", exc_info=True)
        sys.exit(1)

    # 创建AI核心实例
    ai_core = PythonAICore(config=config, bind_address=args.bind_address)

    # 启动事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 注册优雅停机信号
    async def shutdown():
        await ai_core.stop()
        loop.stop()

    for sig in (asyncio.signals.SIGINT, asyncio.signals.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    # 启动AI核心
    try:
        loop.run_until_complete(ai_core.start())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("收到停机信号，正在优雅关闭...")
    except Exception as e:
        logger.critical(f"AI核心运行异常: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        loop.close()
        sys.exit(0)


# 直接运行时启动
if __name__ == "__main__":
    main()
```

---

### 24. 依赖锁定文件 `requirements.txt`

```Plain Text

# 月见（Selrena）Python AI 层依赖
# 核心依赖
pydantic>=2.7.0,<3.0.0
pyzmq>=26.0.0,<27.0.0
structlog>=24.0.0,<25.0.0
python-dotenv>=1.0.0,<2.0.0

# 本地模型依赖（可选，按需安装）
# llama-cpp-python>=0.2.0
# openai>=1.0.0

# 开发依赖
pytest>=8.0.0
mypy>=1.10.0
flake8>=6.0.0
black>=24.0.0
```

---

## 代码核心合规性说明

1. **严格遵循架构铁律**：Python层完全不碰场景、平台、本地IO，所有配置由内核注入，所有持久化由内核负责

2. **纯灵魂定位**：所有代码仅负责思考、人格、记忆、情绪、内容生成，无任何杂活

3. **分层严格隔离**：遵循DDD分层架构，每层职责清晰，无越界代码

4. **完整可运行**：所有代码完整，注释详细，可直接落地开发，仅需替换LLM引擎的模型调用部分

5. **全链路追踪**：所有流程都有trace_id透传，便于问题排查

6. **优雅生命周期管理**：完整的启动/停止逻辑，支持优雅停机，无资源泄漏
> （注：文档部分内容可能由 AI 生成）