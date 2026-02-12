"""
语音识别客户端（ASR Client）

职责：
- 提供语音识别的功能接口。
"""

from typing import Optional, Union, Dict, Any, List
import os
import numpy as np
import torch
from funasr import AutoModel

from cradle.core.config_manager import global_config
from cradle.core.model_manager import global_model_manager
from cradle.utils.logger import logger
from cradle.utils.env import IS_WINDOWS

class FunASRClient:
    """
    FunASR 语音识别客户端 (支持 SenseVoice/Paraformer)
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FunASRClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logger
        # 使用 global_config 获取系统配置
        self.config_manager = global_config
        self.asr_config = self.config_manager.get_system().perception.audio.asr
        self.model: Optional[AutoModel] = None
        self._is_ready = False
        
        # 自动加载模型 (如果启用)
        if self.asr_config.enabled:
            try:
                self.load_model()
            except Exception as e:
                self.logger.error(f"FunASR 自动加载失败：{e}")
        
        self._initialized = True

    def load_model(self):
        """加载 FunASR 模型"""
        if self._is_ready:
            return

        # 使用资源管理器解析模型路径 (自动处理本地路径/远程ID/缓存位置)
        model_name = global_model_manager.resolve_model_path(self.asr_config.model_dir)
        device = self.asr_config.device
        
        # 智能设备回退
        if device == "cuda" and not torch.cuda.is_available():
            self.logger.warning("请求使用 CUDA 但不可用。正在回退到 CPU。")
            device = "cpu"

        self.logger.debug(f"正在加载 FunASR 模型: {model_name} (设备: {device})...")
        
        try:
            # 初始化 AutoModel
            # SenseVoiceSmall 需要特定的参数配置
            load_kwargs = {
                "model": model_name,
                "device": device,
                "disable_update": True,  # 禁止自动检查更新加速启动
                "log_level": "ERROR",
            }

            if self.asr_config.quantize and device == "cuda":
                # 部分模型支持量化加载
                pass 

            self.model = AutoModel(**load_kwargs)
            
            self._is_ready = True
            self.logger.debug("FunASR 模型加载成功。")
            
        except Exception as e:
            self.logger.critical(f"FunASR 模型加载失败: {e}")
            self._is_ready = False
            raise

    def transcribe(self, audio_input: Union[str, np.ndarray, bytes], language: str = "zh") -> str:
        """
        执行语音识别
        :param audio_input: 文件路径 或 Numpy音频数据 (float32/int16)
        :param language: 目标语言 (zh/en/auto)
        :return: 识别文本
        """
        if not self._is_ready or self.model is None:
            self.logger.warning("FunASR 模型尚未就绪。")
            return ""

        try:
            # SenseVoice generate 参数: input, language, use_itn, etc.
            # 注意: 输入数据预处理由 funasr 内部处理，但需确保 numpy 格式正确
            
            # 确保 bytes 转 numpy if needed (假设 raw pcm)
            # 这里的处理逻辑通常交给调用层，或者假定输入已经是合规的
            
            # 构造推理参数
            # 关键修正：禁用 merge_vad。因为我们已经在 stream 层做了精细的 VAD 切割。
            infer_kwargs = {
                "input": audio_input,
                "language": language,
                "use_itn": self.asr_config.use_itn,
                "merge_vad": False,  # 禁用内部 VAD
                "disable_pbar": True, # 禁用 tqdm 进度条 (去除 rtf_avg 输出)
            }
            
            # 仅支持 numpy 数组或文件路径直接推理，不再尝试写入临时文件
            if not (isinstance(audio_input, np.ndarray) or isinstance(audio_input, str)):
                self.logger.error("ASR 仅支持 numpy 数组或文件路径输入，当前类型不支持。")
                return ""
            try:
                results = self.model.generate(**infer_kwargs)
            except Exception as e:
                self.logger.error(f"ASR 推理失败：{e}")
                return ""
            
            # 解析结果
            # SenseVoice 返回通常是 list of dict: [{'text': '...'}]
            if results and isinstance(results, list):
                text = "".join([res.get("text", "") for res in results])
                
                # 简单清洗 (去空格等，视模型而定)
                text = text.replace(" ", "") if language == "zh" else text
                return text
            
            return ""

        except Exception as e:
            self.logger.error(f"ASR Inference Error: {e}")
            return ""
