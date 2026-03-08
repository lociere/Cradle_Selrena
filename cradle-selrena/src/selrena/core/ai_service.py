"""AI服务

连接Python AI核心与TS内核的桥梁服务
处理事件总线通信，调用AI核心处理逻辑
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from .event_bus_client import EventBusClient, EventBusTransport
from selrena.container import AIContainer
from selrena.domain.persona import Persona
from selrena.domain.memory import Memory, MemoryType
from selrena.domain.emotion import EmotionState
from .sensory import SensorySystem
from selrena.inference.engines.utils.preprocessor import MultimodalPreprocessor
from selrena.utils.event_bus import publish as publish_internal

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """AI响应"""
    text: str
    emotion: Optional[EmotionState] = None
    memory_updates: Optional[list[Memory]] = None
    metadata: Optional[Dict[str, Any]] = None


class AIService:
    """
    AI服务
    
    负责：
    1. 监听TS内核发送的事件
    2. 调用Python AI核心处理逻辑
    3. 将响应发送回TS内核
    """
    
    def __init__(
        self,
        event_bus_host: str = "localhost",
        event_bus_port: int = 3000,
        transport: EventBusTransport = EventBusTransport.HTTP,
        config_dir: str | None = None,
        data_dir: str | None = None,
    ):
        """
        初始化AI服务
        
        Args:
            event_bus_host: 事件总线主机地址
            event_bus_port: 事件总线端口
            transport: 传输协议
        """
        self.event_bus = EventBusClient(
            transport=transport,
            host=event_bus_host,
            port=event_bus_port
        )
        
        # 初始化AI容器，允许通过参数传入目录
        if config_dir is not None and data_dir is not None:
            self.ai_container = AIContainer(config_dir=config_dir, data_dir=data_dir)
        else:
            # 如果调用者未指定目录，则使用默认临时路径，方便快速测试
            from pathlib import Path
            cfg = Path("./config_simple")
            data = Path("./data_simple")
            cfg.mkdir(exist_ok=True)
            data.mkdir(exist_ok=True)
            self.ai_container = AIContainer(config_dir=cfg, data_dir=data)
        
        # 注册事件处理器
        self._register_event_handlers()
        
        # 服务状态
        self.is_running = False
        self.current_conversation_id: Optional[str] = None
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 用户输入事件
        self.event_bus.register_handler("user_input", self._handle_user_input)
        
        # 系统事件
        self.event_bus.register_handler("system_start", self._handle_system_start)
        self.event_bus.register_handler("system_stop", self._handle_system_stop)
        
        # 感知事件
        self.event_bus.register_handler("perception_audio", self._handle_perception_audio)
        self.event_bus.register_handler("perception_visual", self._handle_perception_visual)
        
        # 内存操作事件
        self.event_bus.register_handler("memory_query", self._handle_memory_query)
        self.event_bus.register_handler("memory_store", self._handle_memory_store)
        
        logger.info("事件处理器注册完成")
    
    async def start(self):
        """启动AI服务"""
        try:
            # 连接到事件总线
            await self.event_bus.connect()
            
            # 启动事件监听
            self.is_running = True
            asyncio.create_task(self.event_bus.start_listening())
            
            # 发送服务启动事件
            await self.event_bus.send_event("ai_service_started", {
                "service": "python_ai_core",
                "status": "running",
                "capabilities": ["conversation", "memory", "reasoning"]
            })
            
            logger.info("AI服务已启动")
            
        except Exception as e:
            logger.error(f"启动AI服务失败: {e}")
            raise
    
    async def stop(self):
        """停止AI服务"""
        self.is_running = False
        
        # 发送服务停止事件
        await self.event_bus.send_event("ai_service_stopped", {
            "service": "python_ai_core",
            "status": "stopped"
        })
        
        # 断开事件总线连接
        await self.event_bus.disconnect()
        
        logger.info("AI服务已停止")
    
    async def _handle_user_input(self, event: Dict[str, Any]):
        """处理用户输入事件。

        旧架构的 SoulIntellect 会收到各种形式的载荷（外部/内部、视觉/文本等），
        并通过 `MultimodalPreprocessor` 标准化。为了保持契约一致，我们在这里
       复用同样的思路：

        1. 从 payload 提取 content/text 等字段。
        2. 判断是否来自外部源并据此决定是否使用短时记忆。
        3. 预处理去除 CQ 码、占位符等。
        4. 将结果交给 ConversationService。
        """
        try:
            raw = event.get("payload", {}) or {}

            # 兼容老接口：有 message 字段时直接使用；否则将整个载荷交给预处理
            if "message" in raw and raw.get("message"):
                user_id = raw.get("user_id", "default_user")
                conversation_id = raw.get("conversation_id")
                text = raw.get("message", "")
                is_external = raw.get("is_external_source", False)
                content = text
            else:
                # 使用预处理器解析多模态载荷
                text, has_visual, is_valid = MultimodalPreprocessor.validate_ingress_payload(raw)
                user_id = raw.get("user_id", "default_user")
                conversation_id = raw.get("conversation_id")
                is_external = bool(raw.get("is_external_source", False))
                content = raw.get("content", text)

            if not is_valid and not content:
                logger.debug("忽略无效或空消息")
                return

            logger.info(f"收到用户输入: {user_id} - {text[:50]}...")

            if conversation_id:
                self.current_conversation_id = conversation_id

            # 调用AI核心处理用户输入，将 is_external 传递下去
            response = await self._process_user_input(user_id, content, is_external)

            # 发送AI响应事件
            await self.event_bus.send_event("ai_response", {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response": response.text,
                "emotion": asdict(response.emotion) if response.emotion else None,
                "memory_updates": [
                    asdict(memory) for memory in response.memory_updates
                ] if response.memory_updates else [],
                "metadata": response.metadata
            })
            # 同时发布内部事件，供其他Python模块监听
            publish_internal("ai.response", response)

            logger.info(f"已发送AI响应: {response.text[:50]}...")

        except Exception as e:
            logger.error(f"处理用户输入失败: {e}")
            await self.event_bus.send_event("ai_error", {
                "conversation_id": self.current_conversation_id,
                "error": str(e),
                "message": "处理用户输入时发生错误"
            })
    

    async def _handle_system_start(self, event: Dict[str, Any]):
        logger.info("收到 system_start 事件")

    async def _handle_system_stop(self, event: Dict[str, Any]):
        logger.info("收到 system_stop 事件")

    async def _handle_perception_audio(self, event: Dict[str, Any]):
        logger.info("收到 perception_audio 事件")

    async def _handle_perception_visual(self, event: Dict[str, Any]):
        logger.info("收到 perception_visual 事件")

    async def _handle_memory_query(self, event: Dict[str, Any]):
        logger.info("收到 memory_query 事件")

    async def _handle_memory_store(self, event: Dict[str, Any]):
        logger.info("收到 memory_store 事件")

    async def _process_user_input(self, user_id: str, message: str, is_external: bool = False) -> AIResponse:
        """
        处理用户输入，生成AI响应。

        Args:
            user_id: 用户ID
            message: 用户消息（经过预处理的 content）
            is_external: 是否来自外部源, 外部请求不会触发短时记忆维护

        Returns:
            AI响应
        """
        try:
            # 传入感知系统对消息做最后统一处理
            senses = SensorySystem()
            perceived = await senses.perceive({"content": message})
            final_content = perceived.get("content", message)

            # 获取对话服务
            conversation_service = self.ai_container.get_conversation_service()
            
            # 处理对话
            conversation_result = await conversation_service.process_conversation(
                user_id=user_id,
                message=final_content,
                conversation_id=self.current_conversation_id,
                is_external=is_external
            )
            
            # 获取情感状态
            emotion_state = conversation_result.emotion_state
            
            # 获取记忆更新
            memory_updates = []
            if conversation_result.memory_to_store:
                memory_updates.append(conversation_result.memory_to_store)
            
            # 构建响应
            response = AIResponse(
                text=conversation_result.response,
                emotion=emotion_state,
                memory_updates=memory_updates,
                metadata={
                    "reasoning_steps": conversation_result.reasoning_steps,
                    "confidence": conversation_result.confidence
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"处理用户输入时发生错误: {e}")
            
            # 返回错误响应
            return AIResponse(text="error")


# 简化的AI服务（用于快速启动）
class SimpleAIService:
    """
    简化的AI服务
    
    使用HTTP与TS内核通信，适合快速启动和测试
    """
    
    def __init__(self, host: str = "localhost", port: int = 3000,
                 config_dir: str | None = None, data_dir: str | None = None):
        from .event_bus_client import SimpleEventBusClient
        from pathlib import Path
        
        self.event_bus = SimpleEventBusClient(host, port)
        # provide default temporary dirs if none specified
        cfg = Path(config_dir) if config_dir else Path("./config_simple")
        data = Path(data_dir) if data_dir else Path("./data_simple")
        cfg.mkdir(parents=True, exist_ok=True)
        data.mkdir(parents=True, exist_ok=True)
        self.ai_container = AIContainer(config_dir=cfg, data_dir=data)
        self.is_running = False
    
    async def start(self):
        """启动服务"""
        try:
            # 初始化AI容器 (使用默认空配置, 将触发 DummyLLM)
            await self.ai_container.initialize(llm_config={}, use_local_llm=False)
            
            self.is_running = True
            logger.info("简化的AI服务已启动")
            
        except Exception as e:
            logger.error(f"启动简化AI服务失败: {e}")
            raise
    
    async def process_message(self, user_id: str, message: str) -> str:
        """
        处理消息并返回响应
        
        Args:
            user_id: 用户ID
            message: 用户消息
            
        Returns:
            AI响应文本
        """
        try:
            conversation_service = self.ai_container.get_conversation_service()
            
            result = await conversation_service.process_conversation(
                user_id=user_id,
                message=message
            )
            
            return result.response
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return "抱歉，我遇到了一些问题。"
