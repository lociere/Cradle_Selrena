import asyncio
import os
import sys

# -------------------------------------------------------------------------
# Launcher Script (Entry Point)
# 职责: 负责 UI 初始化、环境准备，随后将控制权移交给系统内核 (Kernel)。
# -------------------------------------------------------------------------

async def main():
    # 0. UI 初始化: 立即清屏，保证第一眼视觉体验
    os.system('cls' if os.name == 'nt' else 'clear')

    print("===============================================================")
    print("   系统唤醒序列: CRADLE SELRENA (摇篮: 月见)                   ")
    print("===============================================================")
    print("")
    
    # 1. 移交控制权给内核
    print(">> [系统引导] 正在挂载神经内核...", end="", flush=True)
    
    # 此时才开始加载重型依赖 (Torch, Transformers等)，不会阻塞上方的 UI 显示
    # 这行 import 执行期间，控制台会显示上面的提示，直到加载完成
    from cradle.kernel import boot_sequence
    
    # 覆盖上一行提示，显示完成状态
    print(f"\r>> [系统引导] 正在挂载神经内核... [完成]")
    
    await boot_sequence()

if __name__ == "__main__":
    try:
        # Windows 特定的事件循环策略设置
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

