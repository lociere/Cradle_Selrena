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