"""
AI 核心使用示例

展示如何使用新的架构分层
"""

import asyncio
import os
from pathlib import Path

# 示例 1: 基本对话
async def example_basic_chat():
    """基本对话示例"""
    from selrena import AIContainer
    
    container = AIContainer(
        config_dir=Path("./configs"),
        data_dir=Path("./data")
    )
    
    await container.initialize({
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": "gpt-3.5-turbo",
        "persona": "selrena"
    })
    
    response = await container.chat("你好，请介绍一下你自己")
    print(f"AI: {response}")
    
    await container.cleanup()


# 示例 2: 自定义人设
async def example_custom_persona():
    """自定义人设示例"""
    from selrena.domain.persona import Persona
    from selrena.application import ConversationService
    from selrena.adapters import KernelAdapter, MemoryAdapter
    from selrena.inference.llm import OpenAILLM
    
    # 创建自定义人设
    persona = Persona(
        name="小助手",
        identity="一个专业的工作助手",
        values=["高效", "专业", "可靠"],
        behavior_patterns=["简洁明了", "直奔主题"],
        expression_style={"tone": "专业"}
    )
    
    # 初始化组件
    llm = OpenAILLM(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model="gpt-3.5-turbo"
    )
    
    kernel = KernelAdapter()
    memory = MemoryAdapter(Path("./data/memory"))
    
    # 创建对话服务
    service = ConversationService(
        persona=persona,
        llm=llm,
        kernel=kernel,
        memory=memory
    )
    
    response = await service.process_message("今天的工作计划是什么？")
    print(f"{persona.name}: {response}")
    
    await llm.cleanup()


# 示例 3: 记忆服务
async def example_memory_service():
    """记忆服务示例"""
    from selrena.application import MemoryService
    from selrena.adapters import MemoryAdapter
    from selrena.domain.memory import Memory, MemoryType
    
    memory_adapter = MemoryAdapter(Path("./data/memory"))
    service = MemoryService(memory_adapter)
    
    # 保存记忆
    await service.memorize(
        "用户喜欢喝咖啡",
        memory_type=MemoryType.SEMANTIC,
        tags=["user", "preference"],
        importance=0.8
    )
    
    # 检索记忆
    memories = await service.recall("咖啡")
    for mem in memories:
        print(f"记忆：{mem.content} (重要度：{mem.importance})")


# 示例 4: 推理服务
async def example_reasoning_service():
    """推理服务示例"""
    from selrena.application import ReasoningService
    from selrena.inference.llm import OpenAILLM
    
    llm = OpenAILLM(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model="gpt-3.5-turbo"
    )
    
    service = ReasoningService(llm=llm)
    
    # 文本推理
    response = await service.reason(
        "如何用 Python 实现快速排序？",
        context="用户是一名编程初学者"
    )
    print(f"回答：{response[:200]}...")
    
    await llm.cleanup()


# 示例 5: 自定义内核适配器（Rust 示例）
async def example_custom_kernel_adapter():
    """自定义内核适配器示例"""
    from selrena.ports import KernelPort  # legacy import earlier from cradle_selrena_core (now selrena)
    
    class RustKernelAdapter(KernelPort):
        """Rust 内核适配器示例"""
        
        async def send_message(self, text: str, emotion: str = None):
            # 这里实现与 Rust 内核的通信逻辑
            print(f"[Rust Kernel] 发送消息：{text}")
        
        async def play_audio(self, audio_path: str):
            print(f"[Rust Kernel] 播放音频：{audio_path}")
        
        async def capture_screen(self) -> str:
            print("[Rust Kernel] 截取屏幕")
            return ""
        
        async def read_file(self, path: str) -> str:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        
        async def write_file(self, path: str, content: str) -> None:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    # 使用自定义适配器
    kernel = RustKernelAdapter()
    await kernel.send_message("测试消息", emotion="happy")


if __name__ == "__main__":
    print("=" * 60)
    print("Cradle Selrena Core - 使用示例")
    print("=" * 60)
    print()
    
    # 运行示例（取消注释以运行）
    # asyncio.run(example_basic_chat())
    # asyncio.run(example_custom_persona())
    # asyncio.run(example_memory_service())
    # asyncio.run(example_reasoning_service())
    # asyncio.run(example_custom_kernel_adapter())
    
    print("请取消注释相应的示例来运行")
