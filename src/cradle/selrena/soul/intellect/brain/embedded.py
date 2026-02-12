import asyncio
import os
from typing import List, Dict, Any
from cradle.core.config_manager import global_config
from cradle.schemas.configs.soul import LLMConfig
from cradle.utils.logger import logger
from . import BaseBrainBackend

# 懒加载：避免在模块导入时就检查依赖
try:
    from llama_cpp import Llama
    import llama_cpp
except ImportError:
    Llama = None
    llama_cpp = None

class LlamaCppEmbeddedBackend(BaseBrainBackend):
    """
    本地内嵌神经后端 (In-Process Local LLM)
    基于 llama.cpp，在独立线程中运行推理，通过 asyncio.to_thread 保持主循环流畅。
    """
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._llm = None
        self._lock = asyncio.Lock() # 简单防并发，确保同一时刻只有一个思考在进行

    async def initialize(self):
        if Llama is None:
            raise ImportError(
                "未检测到 'llama_cpp' 库。如需使用本地内嵌模式，请安装: "
                "pip install llama-cpp-python (推荐配合 GPU 使用)"
            )

        # 使用 ModelManager 统一解析/验证模型路径（本地优先；不自动下载）
        from cradle.core.model_manager import global_model_manager
        model_path = global_model_manager.resolve_model_path(self.config.local_model_path, auto_download=False)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"[Local Backend] 模型文件未找到: {model_path} — 请使用 ModelManager 下载或在配置中提供正确路径")

        logger.info(f"[Local Backend] 正在加载神经网络权重... (GPU Layers: {self.config.n_gpu_layers})")
        
        # 这是一个耗时操作(1-5秒)，在启动阶段我们可以接受它阻塞主线程
        # 如果追求极致启动速度，也可以放到线程里去初始化
        try:
            import llama_cpp
            logger.debug(f"[Local Backend] verify llama_cpp path: {llama_cpp.__file__}")

            # --- 动态加载策略 (Dynamic Loading Strategy) ---
            # 优先尝试 "极速模式" (-1)，如果显存(VRAM)不足，自动回退到 "兼容模式" (20)
            
            load_strategies = [
                {
                    "name": "🚀 极速模式 (Full GPU)",
                    "kwargs": {
                        "n_gpu_layers": -1,
                        "flash_attn": True,
                        "type_k": llama_cpp.GGML_TYPE_Q8_0, 
                        "type_v": llama_cpp.GGML_TYPE_Q8_0
                    }
                },
                {
                    "name": "🛡️ 兼容模式 (Partial GPU)",
                    "kwargs": {
                        "n_gpu_layers": 20, 
                        "flash_attn": False, 
                    }
                }
            ]

            is_debug = global_config.get_system().app.debug
            last_error = None
            for strategy in load_strategies:
                try:
                    logger.debug(f"[Local Backend] 尝试加载策略: {strategy['name']}")
                    self._llm = Llama(
                        model_path=model_path,
                        n_ctx=self.config.n_ctx,
                        verbose=is_debug,
                        **strategy["kwargs"]
                    )
                    logger.info(f"[Local Backend] 模型加载成功! | Context: {self.config.n_ctx} | Strategy: {strategy['name']}")
                    break # 成功则跳出循环
                except Exception as e:
                    logger.warning(f"[Local Backend] 策略 {strategy['name']} 加载失败: {e}")
                    last_error = e
                    # 清理刚才失败的实例（如果有），释放显存
                    if self._llm:
                        del self._llm
                        self._llm = None
                    continue
            
            if self._llm is None:
                 logger.critical(f"[Local Backend] 所有加载策略均失败。最后一次错误: {last_error}")
                 raise last_error

        except Exception as e:
            logger.critical(f"[Local Backend] 初始化流程崩溃: {e}")
            raise

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        执行非阻塞推理
        """
        if not self._llm:
            return "（大脑未初始化）"

        async with self._lock:
            # 使用 asyncio.to_thread 将同步的 C++ 调用剥离出去
            # 这里的 create_chat_completion 是 CPU/GPU 密集型任务，会释放 GIL
            try:
                response = await asyncio.to_thread(
                    self._llm.create_chat_completion,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    stream=False # 暂不使用流式，为了架构简单
                )
                return response['choices'][0]['message']['content']
            except Exception as e:
                logger.error(f"[Local Backend] 突触连接中断 (Inference Error): {e}")
                return "（...思考被打断了）"

    async def cleanup(self):
        # llama_cpp 对象析构时会自动释放显存
        self._llm = None
        logger.info("[Local Backend] 神经网络已卸载，显存已释放。")
