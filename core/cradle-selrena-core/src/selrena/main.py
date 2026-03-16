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