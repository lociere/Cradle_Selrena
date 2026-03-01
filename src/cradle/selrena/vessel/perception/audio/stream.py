"""
音频流处理（Audio Stream）

职责：
- 捕获音频流并进行语音活动检测（VAD）。
"""

import asyncio
import numpy as np
import sounddevice as sd
import webrtcvad
import time
from typing import Optional
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.utils.logger import logger

from cradle.core.config_manager import global_config
from cradle.selrena.vessel.perception.audio.asr_client import FunASRClient
from cradle.utils.path import ProjectPath

class AudioStream:
    """
    音频流捕获与VAD(语音活动检测)
    使用 sounddevice 读取麦克风，webrtcvad 检测语音，分段送入 ASR
    """
    def __init__(self):
        self.logger = logger
        # 暂时手动获取 loop，因为 __init__ 可能不在 loop 运行的线程
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None
            
        self.config = global_config.get_system().perception.audio
        self.asr_client = FunASRClient()
        
        # Debug 目录
        self.debug_dir = ProjectPath.LOGS_DIR / "debug_audio"
        self.debug_dir.mkdir(exist_ok=True)


        
        # VAD 设置
        # 降级 VAD 灵敏度已避免切掉首音节 (3 -> 2)
        self.vad = webrtcvad.Vad(2) # 0-3, 3 is most aggressive
        self.sample_rate = 16000 # webrtcvad supports 8k, 16k, 32k, 48k
        self.frame_duration_ms = 30 # 10, 20, or 30ms
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        
        # 状态
        self.is_listening = False
        self.buffer = bytearray()
        self.speech_buffer = bytearray()
        self.is_speech_active = False
        self.silence_frames_count = 0
        self.max_silence_frames = 20 # 约 600ms 静音判定结束
        
        # 4. 唤醒与交互状态管理
        self.last_wake_time = 0
        self.wake_timeout = 30.0  # 唤醒后维持 30秒 活跃状态
        
        # 唤醒词与退出指令 - 已移交 synapse 层处理
        # ...existing code...
        
    def _ensure_loop(self):
         if not self.loop:
             try:
                 self.loop = asyncio.get_running_loop()
             except RuntimeError:
                 self.logger.error("AudioStream needs a running asyncio loop.")

    def _audio_callback(self, indata, frames, time_info, status):
        """SoundDevice 回调 (在独立线程中运行)"""
        if status:
            pass # print(status)
            
        # indata is float32 by default, convert to int16 for webrtcvad
        audio_data = (indata * 32767).astype(np.int16)
        
        # 单声道处理 (indata might be [frames, channels])
        if audio_data.ndim > 1:
            audio_data = audio_data[:, 0]
            
        raw_bytes = audio_data.tobytes()
        
        try:
            is_speech = self.vad.is_speech(raw_bytes, self.sample_rate)
        except Exception:
            is_speech = False

        if is_speech:
            if not self.is_speech_active:
                # self.logger.debug("Detected speech start")
                self.is_speech_active = True
            
            self.silence_frames_count = 0
            self.speech_buffer.extend(raw_bytes)
        else:
            if self.is_speech_active:
                self.silence_frames_count += 1
                self.speech_buffer.extend(raw_bytes) 
                
                if self.silence_frames_count > self.max_silence_frames:
                    # 语音结束
                    self.is_speech_active = False
                    self._process_speech(self.speech_buffer[:])
                    self.speech_buffer.clear()
                    self.silence_frames_count = 0

    def _process_speech(self, audio_bytes):
        """将音频片段提交给 ASR"""
        # if ASR is disabled we simply drop the speech
        if not self.config.asr.enabled:
            return

        # 1. 过滤过短的音频 (小于 0.3秒 可能是杂音)
        # 16k * 2bytes * 0.3秒 = 9600 bytes
        if len(audio_bytes) < 9600:
             return

        # 2. 能量检测 (RMS) - 过滤掉虽然触发VAD但音量极低的底噪
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_int16.astype(np.float64)**2))
        
        # 调试输出能量值
        # self.logger.info(f"🎤 Speech Segment Detected | RMS: {rms:.2f} | Length: {len(audio_bytes)/32000:.2f}s")
        
        # 阈值经验值: 500 (非常安静) - 3000 (正常说话)
        # 如果 RMS 小于 800，通常只是环境底噪
        if rms < 800:
             return

        # 确保有 loop 引用
        if not self.loop:
             return

        # 转换为 Float32 供 ASR 使用 (SenseVoice 需要 float32)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # 3. 智能归一化 (Smart Normalization)
        # 只有当音量确实偏小(但不是纯噪)时才放大，且限制放大倍数，避免把底噪炸成巨响
        max_val = np.max(np.abs(audio_float32))
        
        # 严格控制放大逻辑：
        # 如果 max_val 小于 0.1 (极弱信号)，这通常就是纯底噪，根本不要放大，保持原样甚至可以衰减
        if max_val < 0.1:
            pass # Do nothing
        elif max_val < 0.5:
             # 线性放大到 0.7 左右，但倍数不超过 2
             scale_factor = 0.7 / max_val
             scale_factor = min(scale_factor, 2.0)
             audio_float32 = audio_float32 * scale_factor
        else:
             # 信号足够强，只做轻微衰减防止削波
             audio_float32 = audio_float32 / max_val * 0.95
        
        # ...existing code...

        asyncio.run_coroutine_threadsafe(
            self._transcribe_and_publish(audio_float32), 
            self.loop
        )

    async def _transcribe_and_publish(self, audio_data):
        """异步执行 ASR 并发布事件"""
        if not self.asr_client:
            return

        try:
             # 运行 ASR (切换回 zh 模式，对于中文对话更稳定，配合下方的过滤器)
            text = await asyncio.to_thread(self.asr_client.transcribe, audio_data, language="zh")
        
            if not text or len(text.strip()) == 0:
                return

            # 归一化文本以便匹配 (去标点、转小写)
            import re
            # 保留中文、英文、数字，去除所有标点符号
            text_clean = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text).lower()

            # 逻辑移交: 原始文本直接上报给 Synapse 层
            # Layer2(Edge) 处理外围规整，Reflex 完成门控与意识流编排
            self.logger.debug(f"👂 Transcribed: {text_clean}")
        
            await global_event_bus.publish(BaseEvent(
                name="perception.audio.transcription",
                payload={"text": text, "clean_text": text_clean},
                source="Ear"
            ))
        except Exception as e:
            self.logger.error(f"ASR 任务失败：{e}")

    async def listen_loop(self):
        """启动监听 (替代旧的方法名)"""
        if not self.config.enabled:
            self.logger.info("AudioStream 已禁用，跳过麦克风监听。")
            return
        self.loop = asyncio.get_running_loop()
        await self.start()

    async def start(self):
        """启动监听"""
        if self.is_listening:
            return
            
        device_index = self.config.device_index
        
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                device=device_index,
                channels=1,
                dtype="float32",
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_listening = True
            self.logger.info(f"Microphone listening started (Device: {device_index if device_index is not None else 'Default'}).")
            
            # 保持协程运行，直到停止
            try:
                while self.is_listening:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                self.stop()
                
        except Exception as e:
            self.logger.critical(f"Failed to start microphone stream: {e}")

    def stop(self):
        """停止 SoundDevice 流"""
        if hasattr(self, 'stream') and self.stream:
            if not self.stream.closed:
                self.stream.stop()
                self.stream.close()
            self.stream = None # 避免重复关闭
            
        self.is_listening = False
        self.logger.info("Microphone listening stopped.")

    async def cleanup(self):
        """生命周期钩子: 安全释放音频资源"""
        self.stop()
        self.logger.info("Audio system cleaned up.")

# 兼容旧代码接口 - 原 SemanticEar
SemanticEar = AudioStream
