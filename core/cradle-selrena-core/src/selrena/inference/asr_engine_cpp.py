import ctypes
import os
import platform
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class ASREngineCPP:
    _instance = None
    _lib = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ASREngineCPP, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path: str = None):
        """
        初始化ASR包装器，但不加载模型。模型在首次调用 recognize 时加载。
        """
        if not hasattr(self, 'initialized'):
             self.model_path = model_path
             self.initialized = True
             self._lib_path = self._get_library_path()

    def _get_library_path(self) -> Path:
        """获取本地库路径"""
        system = platform.system()
        lib_name = "selrena_asr"
        if system == "Windows":
             lib_name += ".dll"
        elif system == "Linux":
             lib_name = "lib" + lib_name + ".so"
        else:
             raise RuntimeError(f"Unsupported platform: {system}")
        
        # 假设编译后的库在 core/native/build 或同级目录下
        base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "native" / "build"
        return base_path / lib_name

    def initialize_ASR(self):
        """显式初始化模型（可选，lazy loading会自动调用）"""
        if not self._lib and self._lib_path.exists():
            try:
                self._lib = ctypes.CDLL(str(self._lib_path))
                
                # void* asr_init(const char* model_path)
                self._lib.asr_init.argtypes = [ctypes.c_char_p]
                self._lib.asr_init.restype = ctypes.c_void_p

                # void asr_free(void* handle)
                self._lib.asr_free.argtypes = [ctypes.c_void_p]
                self._lib.asr_free.restype = None

                # char* asr_recognize(void* handle, const char* audio_path)
                self._lib.asr_recognize.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                self._lib.asr_recognize.restype = ctypes.c_char_p # 返回识别出的字符串
                
                logger.info("ASR Native library loaded successfully.")
                
                if self.model_path:
                     encoded_path = str(self.model_path).encode('utf-8')
                     self.handle = self._lib.asr_init(encoded_path)
                else:
                     logger.warning("No model path provided for ASR.")

            except Exception as e:
                logger.error(f"Failed to load ASR library: {e}")
                raise
        elif not self._lib_path.exists():
             logger.warning(f"ASR Native library not found at: {self._lib_path}. ASR will be unavailable.")


    def recognize(self, audio_path: str) -> str:
        """
        识别语音 (同步阻塞调用，外层需使用 executor)
        :param audio_path: 音频文件的路径
        :return: 识别出的文本
        """
        # Lazy Loading
        if not hasattr(self, 'handle'):
            self.initialize_ASR()

        if not self._lib or not hasattr(self, 'handle') or not self.handle:
            logger.error("ASR engine not initialized.")
            return ""

        logger.info(f"Recognizing audio: {audio_path}...")
        result_ptr = self._lib.asr_recognize(
            self.handle,
            str(audio_path).encode('utf-8')
        )
        
        if result_ptr:
            result_str = ctypes.string_at(result_ptr).decode('utf-8')
            # 这里的内存通常由C++层管理，但最好提供一个free_string的接口来避免泄漏
            return result_str
        
        return ""

    def __del__(self):
        if hasattr(self, '_lib') and self._lib and hasattr(self, 'handle') and self.handle:
            self._lib.asr_free(self.handle)
