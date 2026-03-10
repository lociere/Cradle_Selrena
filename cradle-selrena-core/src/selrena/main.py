"""进程入口：启动/停止 AI 核心。

此文件由内核层调用，通常通过 PyInstaller 打包为独立可执行文件。
"""

from __future__ import annotations

import asyncio

from .ai_core import PythonAICore


def main():
    core = PythonAICore()
    async def _run():
        await core.start()
        # placeholder: 监听信号等
        await core.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
