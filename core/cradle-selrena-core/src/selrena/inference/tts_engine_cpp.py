import ctypes
import os
import platform
import logging
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class TTSEngineCPP:
    _instance = None
    _lib = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TTSEngineCPP, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path: str = None):
        """
        初始化TTS包装器，但不加载模型。模型在首次调用 synthesize 时加载。
        """
        if not hasattr(self, 'initialized'):
             self.model_path = model_path
             self.initialized = True
             self._lib_path = self._get_library_path()

    def _get_library_path(self) -> Path:
        """获取本地库路径"""
        system = platform.system()
        lib_name = "selrena_tts"
        if system == "Windows":
             lib_name += ".dll"
        elif system == "Linux":
             lib_name = "lib" + lib_name + ".so"
        else:
             raise RuntimeError(f"Unsupported platform: {system}")
        
        # 假设编译后的库在 core/native/build 或同级目录下
        # 这里需要根据实际部署位置调整，开发环境下可能在 build/
        # core/cradle-selrena-core/src/selrena/inference/ -> core/native/build
        base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "native" / "build"
        return base_path / lib_name

    def _load_library(self):
        """加载 C++ 共享库"""
        if self._lib:
            return

        if not self._lib_path.exists():
            # 在开发阶段，如果找不到库，可以mock或者抛出更友好的错误
            logger.warning(f"TTS Native library not found at: {self._lib_path}. TTS will be unavailable.")
            return

        try:
            self._lib = ctypes.CDLL(str(self._lib_path))
            
            # 定义函数签名
            # void* tts_init(const char* model_path)
            self._lib.tts_init.argtypes = [ctypes.c_char_p]
            self._lib.tts_init.restype = ctypes.c_void_p

            # void tts_free(void* handle)
            self._lib.tts_free.argtypes = [ctypes.c_void_p]
            self._lib.tts_free.restype = None

            # int tts_synthesize(void* handle, const char* text, const char* out_path)
            self._lib.tts_synthesize.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
            self._lib.tts_synthesize.restype = ctypes.c_int
            
            logger.info("TTS Native library loaded successfully.")
            
        except Exception as e:
            logger.error(f"Failed to load TTS library: {e}")
            raise

    def initialize_model(self):
        """显式初始化模型（可选，lazy loading会自动调用）"""
        if not self._lib:
            self._load_library()
        
        if self._lib and not hasattr(self, 'handle'):
             logger.info(f"Initializing TTS model from: {self.model_path}")
             if self.model_path:
                 encoded_path = str(self.model_path).encode('utf-8')
                 self.handle = self._lib.tts_init(encoded_path)
             else:
                 logger.error("No model path provided for TTS.")

    def synthesize(self, text: str, output_path: str) -> bool:
        """
        合成语音 (同步阻塞调用，外层需使用 executor)
        :param text: 要合成的文本
        :param output_path: 输出音频文件的路径
        :return: 是否成功
        """
        # Lazy Loading
        if not hasattr(self, 'handle'):
            self.initialize_model()

        if not self._lib or not hasattr(self, 'handle') or not self.handle:
            logger.error("TTS engine not initialized.")
            return False

        logger.info(f"Synthesizing text: {text[:20]}...")
        result = self._lib.tts_synthesize(
            self.handle,
            text.encode('utf-8'),
            str(output_path).encode('utf-8')
        )
        
        return result == 0

    def __del__(self):
        if hasattr(self, '_lib') and self._lib and hasattr(self, 'handle') and self.handle:
            self._lib.tts_free(self.handle)
