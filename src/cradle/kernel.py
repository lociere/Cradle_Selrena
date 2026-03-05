import asyncio

from cradle.core.config_manager import global_config
from cradle.core.lifecycle import global_lifecycle
# 核心组件导入
from cradle.selrena.soul import SoulIntellect
from cradle.selrena.synapse.edge import Edge
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.selrena.synapse.reflex import Reflex
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient
from cradle.selrena.vessel.napcat.napcat_server import NapcatServer
from cradle.selrena.vessel.perception.audio.stream import SemanticEar
from cradle.selrena.vessel.presentation.audio.player import VirtualMouth
# 标准的顶层导入
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath

# 加载环境
# load_dotenv() - 由 cradle.core.env_config 统一管理


async def boot_sequence():
    """
    CRADLE 系统内核启动序列 (System Boot Sequence)。
    
    按照架构层次自底向上初始化：
    Phase 1: 系统引导 → Phase 2: 核心层 → Phase 3: 感知层 → Phase 4: 表达层 → Phase 5: 服务启动
    """
    # 确保项目目录结构完整
    ProjectPath.ensure_dirs()

    # =========================================================================
    # Phase 1: 系统引导 (SYSTEM BOOTSTRAP)
    # =========================================================================
    print(">> [Phase 1] 系统引导 (SYSTEM BOOTSTRAP)")
    print(
        f"[OK] 系统配置已加载 | {global_config.app.app_name} v{global_config.app.version}")
    print(f"[OK] 项目路径已初始化 | 根目录：{ProjectPath.PROJECT_ROOT}")
    logger.info("系统引导完成")

    # =========================================================================
    # Phase 2: 核心层初始化 (CORE LAYER)
    # =========================================================================
    print("\n>> [Phase 2] 核心层初始化 (CORE LAYER)")
    
    # Step 2.1: 灵魂系统 (The Soul) - 人格、记忆、大脑
    print("  └─ [2.1] 灵魂系统 (Soul System)")
    soul = SoulIntellect(config=global_config.get_soul())
    await soul.initialize()
    
    # Step 2.2: 神经中枢 (The Synapse) - 事件总线、反射、边缘层
    print("  └─ [2.2] 神经中枢 (Synapse System)")
    reflex = Reflex()
    edge = Edge()
    await reflex.initialize()
    await edge.initialize()
    logger.info("核心层初始化完成")

    # =========================================================================
    # Phase 3: 感知层初始化 (PERCEPTION LAYER - VESSEL)
    # =========================================================================
    print("\n>> [Phase 3] 感知层初始化 (PERCEPTION LAYER)")
    
    # Step 3.1: 视觉皮层 (Visual Cortex)
    if global_config.get_system().perception.vision.enabled:
        print("  └─ [3.1] 视觉系统 (Visual System) [已启用]")
        # VisualCortex 已在 Soul 初始化时通过 Brain 注入
    
    # Step 3.2: 听觉系统 (Auditory System)
    ear = None
    if global_config.get_system().perception.audio.enabled:
        print("  └─ [3.2] 听觉系统 (Auditory System) [已启用]")
        ear = SemanticEar()
    else:
        print("  └─ [3.2] 听觉系统 (Auditory System) [已禁用]")
    
    # Step 3.3: 外部感知适配器 (External Perception Adapters)
    cfg = global_config.get_system().napcat
    if cfg.enable:
        print("  └─ [3.3] Napcat 适配器 (Napcat Adapter) [已启用]")
        napcat_server = NapcatServer()
        await napcat_server.initialize()
        napcat_client = NapcatClient(brain=soul.brain)
        await napcat_client.initialize()
    else:
        print("  └─ [3.3] Napcat 适配器 (Napcat Adapter) [已禁用]")
        napcat_server = None
        napcat_client = None
    
    logger.info("感知层初始化完成")

    # =========================================================================
    # Phase 4: 表达层初始化 (PRESENTATION LAYER - VESSEL)
    # =========================================================================
    print("\n>> [Phase 4] 表达层初始化 (PRESENTATION LAYER)")
    
    # Step 4.1: 语音合成 (Text-to-Speech)
    mouth = None
    if global_config.get_system().presentation.tts.enabled:
        print("  └─ [4.1] 语音合成系统 (TTS System) [已启用]")
        mouth = VirtualMouth()
    else:
        print("  └─ [4.1] 语音合成系统 (TTS System) [已禁用]")
    
    # Step 4.2: 虚拟形象 (Virtual Avatar - VTS)
    if global_config.get_system().presentation.vts.enabled:
        print("  └─ [4.2] 虚拟形象系统 (VTS System) [已启用]")
        # VTS 初始化逻辑 (未来扩展)
    else:
        print("  └─ [4.2] 虚拟形象系统 (VTS System) [已禁用]")
    
    logger.info("表达层初始化完成")

    # =========================================================================
    # Phase 5: 服务启动 (SERVICE LAUNCH)
    # =========================================================================
    print("\n>> [Phase 5] 服务启动 (SERVICE LAUNCH)")
    
    # Step 5.1: 启动后台感知任务
    ear_task = None
    if ear:
        ear_task = asyncio.create_task(ear.listen_loop())
        print("  └─ [5.1] 听觉后台任务已启动")
    
    # Step 5.2: 注册生命周期管理
    # [优化] 各组件已在初始化时自行注册到 global_lifecycle，实现依赖倒置
    print("  └─ [5.2] 生命周期管理已注册 | 销毁顺序：LIFO")
    
    # Step 5.3: 系统就绪
    print("\n" + "=" * 63)
    print("   系统在线 | 感官已连接 | 等待输入中...")
    print("=" * 63)
    logger.info("系统主循环已就绪，等待终止信号...")

    # =========================================================================
    # 主循环：阻塞等待关闭信号
    # =========================================================================
    try:
        await global_lifecycle.wait_for_shutdown()
    except asyncio.CancelledError:
        pass
    finally:
        # 清理：取消听觉后台任务
        if ear and not ear_task.done():
            ear_task.cancel()
            logger.info("听觉后台任务已停止")
