"""
配置管理器使用示例

演示如何在新架构中使用配置管理器
"""

import asyncio
from selrena.core.config_manager import global_config


async def example_basic_usage():
    """基础使用示例"""
    
    # 1. 获取完整配置对象
    sys_config = global_config.get_system()
    brain_config = global_config.get_brain()
    
    print(f"应用名称：{sys_config.app.app_name}")
    print(f"调试模式：{sys_config.app.debug}")
    print(f"核心大脑：{brain_config.strategy.get('core_provider')}")
    
    # 2. 使用点分路径获取配置
    debug_mode = global_config.get('app.debug')
    core_provider = global_config.get('strategy.core_provider')
    wake_words = global_config.get('napcat.wake_words')
    
    print(f"\n调试模式 (路径访问): {debug_mode}")
    print(f"核心大脑 (路径访问): {core_provider}")
    print(f"唤醒词列表：{wake_words}")
    
    # 3. 使用便捷属性
    print(f"\n应用配置：{global_config.app}")
    # 假设 persona 信息存放在 brain_config.persona
    print(f"人设名称：{global_config.get_brain().persona.get('name')}")
    # memory 存放在 sys_config or other section; adjust as needed
    print(f"记忆启用：{global_config.get('memory.enabled')}")


async def example_config_sync():
    """配置同步示例"""
    
    # 模拟从内核接收到的配置数据
    sys_config_data = {
        "app": {
            "version": "0.2.0",
            "debug": True,
            "app_name": "Cradle_Selrena",
            "log_level": "DEBUG"
        },
        "napcat": {
            "enable": True,
            "account": 123456789,
            "wake_words": ["月见", "Selrena"]
        }
    }
    
    brain_config_data = {
        "strategy": {
            "routing_mode": "split_tasks",
            "core_provider": "qwen",
            "fallback_to_local": True
        },
        "persona": {
            "name": "月见",
            "role": "伴侣"
        }
    }
    
    # 同步配置
    await global_config.sync_from_kernel(sys_config_data, brain_config_data)
    
    # 验证同步结果
    print(f"\n同步后版本：{global_config.app.version}")
    print(f"同步后调试：{global_config.app.debug}")
    print(f"同步后核心：{global_config.get_brain().strategy.get('core_provider')}")


def example_observer_pattern():
    """观察者模式示例"""
    
    def on_config_changed():
        print("\n[观察者] 配置已变更！")
        print(f"  新版本：{global_config.app.version}")
        print(f"  新调试：{global_config.app.debug}")
    
    # 注册观察者
    global_config.add_observer(on_config_changed)
    
    # 模拟配置更新（实际由内核触发）
    # global_config._notify_observers()


async def main():
    print("=" * 60)
    print("配置管理器使用示例")
    print("=" * 60)
    
    print("\n【示例 1: 基础使用】")
    await example_basic_usage()
    
    print("\n\n【示例 2: 配置同步】")
    await example_config_sync()
    
    print("\n\n【示例 3: 观察者模式】")
    example_observer_pattern()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
