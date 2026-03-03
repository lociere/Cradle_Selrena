import asyncio
import os
from typing import List

from cradle.core.config_manager import global_config
from cradle.schemas.configs.soul import LLMConfig
from cradle.schemas.domain.chat import Message as ChatMessage
from cradle.utils.logger import logger

from .base import BaseBrainBackend
from .utils.sanitizer import PayloadSanitizer

# 懒加载：避免在模块导入时就检查依赖
try:
    import llama_cpp
    from llama_cpp import Llama
    # 尝试导入多模态支持handler (llama-cpp-python >= 0.2.23)
    try:
        from llama_cpp.llama_chat_format import Llava15ChatHandler
    except ImportError:
        Llava15ChatHandler = None
except ImportError:
    Llama = None
    llama_cpp = None
    Llava15ChatHandler = None


class LlamaCppEmbeddedBackend(BaseBrainBackend):
    """
    本地内嵌神经后端 (In-Process Local LLM)
    基于 llama.cpp，在独立线程中运行推理，通过 asyncio.to_thread 保持主循环流畅。
    """

    # --- Initialization ---

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._llm = None
        self._is_multimodal = False
        self._lock = asyncio.Lock()  # 简单防并发，确保同一时刻只有一个思考在进行

    async def initialize(self):
        if Llama is None:
            raise ImportError(
                "未检测到 'llama_cpp' 库。如需使用本地内嵌模式，请安装: "
                "pip install llama-cpp-python (推荐配合 GPU 使用)"
            )

        # 使用 ModelManager 统一解析/验证模型路径（本地优先；不自动下载）
        from cradle.core.model_manager import global_model_manager

        # 1. Resolve Main Model Path
        model_path = global_model_manager.resolve_model_path(
            self.config.local_model_path, auto_download=bool(self.config.auto_download))
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"[Local Backend] 模型文件未找到: {model_path}")

        # 2. Resolve CLIP Projector Path (Optional)
        chat_handler = None
        if self.config.local_clip_model_path and Llava15ChatHandler:
            clip_path = global_model_manager.resolve_model_path(
                self.config.local_clip_model_path, auto_download=bool(self.config.auto_download))
            if os.path.exists(clip_path):
                logger.info(f"[Local Backend] 正在加载视觉投影器 (CLIP): {clip_path}")
                try:
                    # 初始化多模态处理器 (Llava v1.5/1.6 兼容)
                    chat_handler = Llava15ChatHandler(clip_model_path=clip_path)
                    self._is_multimodal = True
                except Exception as e:
                    logger.error(f"[Local Backend] CLIP 加载失败，回退至纯文本模式: {e}")
            else:
                logger.warning(f"[Local Backend] 未找到指定的 CLIP 模型: {clip_path}")
        elif self.config.local_clip_model_path and not Llava15ChatHandler:
            logger.warning("[Local Backend] 请升级 llama-cpp-python 以支持多模态 (Llava15ChatHandler not found)")

        logger.info(
            f"[Local Backend] 正在加载神经网络权重... (GPU Layers: {self.config.n_gpu_layers}) [Multimodal: {self._is_multimodal}]")

        # 这是一个耗时操作(1-5秒)，在启动阶段我们可以接受它阻塞主线程
        try:
            logger.debug(
                f"[Local Backend] verify llama_cpp path: {llama_cpp.__file__}")

            # --- 动态加载策略 (Dynamic Loading Strategy) ---
            # 优先尝试 "用户配置"，如果失败则尝试回退策略
            
            # 从配置中提取用户偏好
            user_n_gpu_layers = self.config.n_gpu_layers
            user_flash_attn = self.config.flash_attn
            user_n_batch = self.config.n_batch

            load_strategies = [
                {
                    "name": "🔧 用户自定义配置 (User Config)",
                    "kwargs": {
                        "n_gpu_layers": user_n_gpu_layers,
                        "n_batch": user_n_batch,
                        "flash_attn": user_flash_attn,
                        "type_k": llama_cpp.GGML_TYPE_Q8_0,  # 显存优化
                        "type_v": llama_cpp.GGML_TYPE_Q8_0
                    }
                },
                {
                    "name": "🚀 极速模式 (Full GPU)",
                    "kwargs": {
                        "n_gpu_layers": -1,
                        "n_batch": 1024,
                        "flash_attn": False, # 为了兼容性，这里改为 False，用户想开可以在配置里开
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
                    logger.debug(
                        f"[Local Backend] 尝试加载策略: {strategy['name']}")
                    
                    # 注入 chat_handler
                    init_kwargs = strategy["kwargs"].copy()
                    if chat_handler:
                        init_kwargs["chat_handler"] = chat_handler
                        # 多模态模型通常需要更大的上下文来容纳图像 embedding
                        # LLaVA 1.5 image context ~576 tokens
                        min_ctx = max(self.config.n_ctx, 2048) 
                    else:
                        min_ctx = self.config.n_ctx

                    self._llm = Llama(
                        model_path=model_path,
                        n_ctx=min_ctx,
                        verbose=is_debug,
                        **init_kwargs
                    )
                    
                    logger.info(
                        f"[Local Backend] 模型加载成功! | Context: {min_ctx} | Vision: {'ON' if chat_handler else 'OFF'}")
                    break  # 成功则跳出循环
                except Exception as e:
                    logger.warning(
                        f"[Local Backend] 策略 {strategy['name']} 加载失败: {e}")
                    last_error = e
                    # 清理刚才失败的实例（如果有），释放显存
                    if self._llm:
                        del self._llm
                        self._llm = None
                    continue

            if self._llm is None:
                logger.critical(
                    f"[Local Backend] 所有加载策略均失败。最后一次错误: {last_error}")
                raise last_error

        except Exception as e:
            logger.critical(f"[Local Backend] 初始化流程崩溃: {e}")
            raise

    async def cleanup(self):
        # llama_cpp 对象析构时会自动释放显存
        self._llm = None
        self._is_multimodal = False
        logger.info("[Local Backend] 神经网络已卸载，显存已释放。")

    @property
    def is_multimodal(self) -> bool:
        return self._is_multimodal

    # --- Core Logic ---

    async def generate(self, messages: List[ChatMessage]) -> str:
        """
        执行非阻塞推理
        """
        if not self._llm:
            return "（大脑未初始化）"

        # [Sanitization]
        # 如果当前后端不支持多模态，必须将图片/音频降级为纯文本，否则会导致 llama-cpp 崩溃或乱码
        if not self._is_multimodal:
            messages = PayloadSanitizer.sanitize_for_text_core(messages)
            
        # 转换为 LlamaCpp 兼容的 Dict 格式
        chat_messages = PayloadSanitizer.to_llm_payload(messages)

        async with self._lock:
            # 使用 asyncio.to_thread 将同步的 C++ 调用剥离出去
            # 这里的 create_chat_completion 是 CPU/GPU 密集型任务，会释放 GIL
            try:
                response = await asyncio.to_thread(
                    self._llm.create_chat_completion,
                    messages=chat_messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    repeat_penalty=getattr(self.config, 'repetition_penalty', 1.1),
                    stream=False  # 暂不使用流式，为了架构简单
                )
                return response['choices'][0]['message']['content']
            except Exception as e:
                logger.error(f"[Local Backend] 突触连接中断 (Inference Error): {e}")
                return "（...思考被打断了）"
