import asyncio

# 标准的顶层导入 
from cradle.utils.logger import logger
from cradle.core.lifecycle import global_lifecycle
from cradle.core.config_manager import global_config
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.path import ProjectPath

# 核心组件导入
from cradle.selrena.soul.intellect.client import SoulIntellect
from cradle.selrena.vessel.perception.audio.stream import SemanticEar
from cradle.selrena.vessel.presentation.audio.player import VirtualMouth
from cradle.selrena.synapse.reflex import Reflex
from cradle.selrena.synapse.edge import Edge
from cradle.selrena.synapse.napcat_server import NapcatServer
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient

# 加载环境
# load_dotenv() - 由 cradle.core.env_config 统一管理

async def boot_sequence():
    """
    CRADLE 系统内核启动序列
    """
    # 确保项目目录结构完整
    ProjectPath.ensure_dirs()
    
    # 1. 内核引导 (KERNEL BOOTSTRAP)
    print(">> [阶段 0] 内核引导 (KERNEL BOOTSTRAP)")
    print(f"[信息] 正在加载系统配置... [完成] ({global_config.app.app_name} v{global_config.app.version})")
    print(f"[信息] 正在初始化神经中枢... [就绪]")
    
    ear = None
    
    # 2. 实例化各个组件
    try:
        print("\n>> [阶段 1] 灵魂注入 (GHOST INJECTION)")
        # Step 1: 灵魂注入 (The Soul)
        soul = SoulIntellect()
        await soul.initialize() 

        print("\n>> [阶段 2] 神经同步 (NEURAL SYNCHRONIZATION)")
        # Step 2: 神经构建 (The Synapse)
        reflex = Reflex()
        edge = Edge()
        await reflex.initialize()
        await edge.initialize()

        # Napcat 连接：目前仅支持服务器模式，Selrena 监听客户端        napcat_client_obj = None
        napcat = None
        cfg = global_config.get_system().napcat
        if cfg.enable:
            napcat = NapcatServer()
            await napcat.initialize()
            # high-level client still useful to parse incoming events
            napcat_client_obj = NapcatClient()
            await napcat_client_obj.initialize()
        else:
            logger.debug("Napcat 已禁用，跳过初始化")
        
        print("\n>> [阶段 3] 躯壳具象化 (SHELL MATERIALIZATION)")
        # Step 3: 躯壳重构 (The Vessel)
        # create output/input devices only if enabled
        mouth = None
        ear = None
        if global_config.get_system().presentation.tts.enabled:
            mouth = VirtualMouth()
        if global_config.get_system().perception.audio.enabled:
            ear = SemanticEar()
        
        # 3. 注册生命周期
        global_lifecycle.register(soul)    # Last OUT
        global_lifecycle.register(edge)
        global_lifecycle.register(reflex)
        global_lifecycle.register(napcat)
        if napcat_client_obj:
            global_lifecycle.register(napcat_client_obj)
        if mouth:
            global_lifecycle.register(mouth)
        if ear:
            global_lifecycle.register(ear)     # First OUT
        
    except Exception as e:
        logger.critical(f"内核启动失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n===============================================================")
    print("   系统在线: 感官已连接 | 等待输入中...                        ")
    print("===============================================================")
    
    # 4. 启动后台感知任务
    ear_task = None
    if ear:
        ear_task = asyncio.create_task(ear.listen_loop())
    
    # 5. 阻塞等待关闭信号
    try:
        await global_lifecycle.wait_for_shutdown()
    except asyncio.CancelledError:
        pass
    finally:
        if ear and not ear_task.done():
            ear_task.cancel()
