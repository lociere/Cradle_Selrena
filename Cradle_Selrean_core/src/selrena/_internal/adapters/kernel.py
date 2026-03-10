# 该文件已使用手工方式格式化，所有注释均为中文
"""实现了 KernelPort 与 AgentPort 接口的内核适配器。

当 Python AI 核心通过事件总线与 TypeScript/Rust 内核通信时
使用此适配器。该类同时作为 MCP 命令的 AgentPort 实现。
"""

from typing import Optional, Any
import asyncio

from selrena._internal.ports.kernel_port import KernelPort
from selrena._internal.ports.agent import AgentPort
from loguru import logger


class KernelAdapter(KernelPort, AgentPort):
    """用于外部内核通信的适配器。

    同时实现 KernelPort（用于普通消息）和 AgentPort
    （用于 MCP 命令）。
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        logger.info("KernelAdapter 初始化 (TS 内核)")

    async def send_message(self, text: str, emotion: Optional[str] = None) -> None:
        from selrena._internal.schemas.events import SpeakAction, ChannelReplyAction

        action = SpeakAction(
            source="AI",
            text=text,
            emotion=emotion or "neutral",
        )
        if self.event_bus:
            await self.event_bus.publish(action)
            logger.debug(f"Message sent over event bus: {text[:50]}...")
        else:
            logger.info(f"[KernelAdapter] {text}")
            print(f"AI output: {text}")

    async def play_audio(self, audio_path: str) -> None:
        """播放指定音频文件（占位实现）。"""
        logger.info(f"KernelAdapter playing audio: {audio_path}")

    async def capture_screen(self) -> str:
        """截取屏幕并返回文件路径（存根）。"""
        logger.info("KernelAdapter capturing screen (stub)")
        return ""

    async def read_file(self, path: str) -> str:
        return await asyncio.to_thread(
            __import__("pathlib").Path(path).read_text, encoding="utf-8"
        )

    async def write_file(self, path: str, content: str) -> None:
        await asyncio.to_thread(
            __import__("pathlib").Path(path).write_text, content, encoding="utf-8"
        )

    # AgentPort implementation ------------------------------------------------
    async def send_command(self, command: dict[str, Any]) -> None:
        """通过事件总线将 MCP 命令字典转发给内核。"""
        from selrena._internal.schemas.events import MCPCommandAction

        if self.event_bus:
            action = MCPCommandAction(command=command)
            await self.event_bus.publish(action)
        else:
            logger.debug(f"[KernelAdapter] command: {command}")
