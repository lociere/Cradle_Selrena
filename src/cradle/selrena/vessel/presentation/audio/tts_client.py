"""
TTS 客户端（TTS Client)

职责：
- 提供文本转语音（TTS）的功能接口。
"""

import asyncio
import subprocess
import re
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import edge_tts
except ImportError:
    edge_tts = None

from cradle.core.config_manager import global_config
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.utils.string import sanitize_text

class BaseTTSClient:
    def __init__(self):
        self.config = global_config.get_system().presentation.tts
        self._player_process: Optional[subprocess.Popen] = None
        self._ensure_output_dir()
        
    def _ensure_output_dir(self):
        out_dir = self._resolve_path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            return ProjectPath.PROJECT_ROOT / p
        return p

    def _build_filename(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"tts_{ts}.wav"

    def stop(self):
        if self._player_process and self._player_process.poll() is None:
            self._player_process.terminate()
            self._player_process = None

    def play(self, audio_path: Path):
        if not audio_path or not audio_path.exists():
            return
        if not self.config.auto_play:
            return
        self.stop()
        try:
            # Using ffplay for universal playback (requires ffmpeg installed)
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
            self._player_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"[TTS] 播放失败: {e}")

    async def synthesize(self, text: str) -> Optional[Path]:
        raise NotImplementedError

class GPTSoVITSClient(BaseTTSClient):
    """
    GPT-SoVITS 从属客户端
    特点: 高质量情感克隆，需外部 API
    """
    def __init__(self):
        super().__init__()
        self.presets = self._load_presets()

    def _load_presets(self) -> Dict[str, Any]:
        preset_path = self._resolve_path(self.config.character_map_path)
        if not preset_path.exists():
            return {}
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _analyze_emotion(self, text: str) -> Tuple[str, str]:
        # 简单提取 [happy] 标签
        emotion = "calm"
        match = re.search(r"\[(.*?)\].*", text, re.DOTALL)
        clean_text = sanitize_text(text)
        
        if match:
            tag = match.group(1).lower()
            emotions = self.presets.get("emotions", {})
            for key in emotions:
                if key in tag:
                    emotion = key
                    break
        return clean_text, emotion

    async def synthesize(self, text: str) -> Optional[Path]:
        clean_text, emotion = self._analyze_emotion(text)
        if not clean_text: return None

        emotions_config = self.presets.get("emotions", {})
        base_path_str = self.presets.get("base_path", "")
        
        # 降级策略
        target_emo = emotion if emotion in emotions_config else "calm"
        if target_emo not in emotions_config and emotions_config:
            target_emo = list(emotions_config.keys())[0] # Pick first available
            
        if target_emo not in emotions_config:
            logger.warning("[TTS] GPT-SoVITS 缺少情感配置，无法合成")
            return None

        emo_data = emotions_config[target_emo]
        ref_wav_path = Path(base_path_str) / emo_data["file"]
        if not ref_wav_path.is_absolute():
            ref_wav_path = ProjectPath.PROJECT_ROOT / base_path_str / emo_data["file"] # Fix path join

        payload = {
            "text": clean_text,
            "text_lang": "zh",
            "ref_audio_path": str(ref_wav_path.absolute()),
            "prompt_text": emo_data["prompt"],
            "prompt_lang": emo_data["lang"],
        }

        api_url = f"{self.config.api_url.rstrip('/')}/tts"
        out_path = self._resolve_path(self.config.output_dir) / self._build_filename()

        try:
            # 兼容 requests 阻塞调用
            loop = asyncio.get_running_loop()
            
            def _request():
                try:
                    resp = requests.post(api_url, json=payload, timeout=30)
                except:
                    # Try GET fallback
                    params = {k:v for k,v in payload.items()}
                    resp = requests.get(api_url, params=params, timeout=30)
                return resp

            response = await loop.run_in_executor(None, _request)

            if response.status_code == 200:
                logger.debug(f"[TTS] GPT-SoVITS 返回内容长度: {len(response.content)} 字节")
                if not response.content or len(response.content) < 1024:
                    logger.error(f"[TTS] GPT-SoVITS 返回内容为空或过小，未生成音频文件。Headers: {response.headers} Text: {response.text[:200]}")
                    return None
                with open(out_path, "wb") as f:
                    f.write(response.content)
                logger.debug(f"[TTS] GPT-SoVITS 合成: {out_path}")
                return out_path
            else:
                logger.error(f"[TTS] GPT-SoVITS API Error: {response.text}")
        except Exception as e:
            logger.error(f"[TTS] GPT-SoVITS 连接失败: {e}")
        
        return None

class EdgeTTSClientEngine(BaseTTSClient):
    """
    Edge-TTS 本地客户端
    特点: 轻量、无需本地模型，但依赖网络
    """
    async def synthesize(self, text: str) -> Optional[Path]:
        if not text:
            return None

        if not edge_tts:
            logger.error("[TTS] edge-tts 未安装，请运行 pip install edge-tts")
            return None

        clean_text = sanitize_text(text)
        if not clean_text:
            return None

        out_path = self._resolve_path(self.config.output_dir) / self._build_filename()
        try:
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=self.config.voice,
                rate=self.config.rate,
                volume=self.config.volume,
                pitch=self.config.pitch,
            )
            await communicate.save(str(out_path))
            logger.debug(f"[TTS] Edge-TTS 合成: {out_path}")
            return out_path
        except Exception as e:
            logger.error(f"[TTS] Edge-TTS 合成失败: {e}")
            return None

class UnifiedTTSClient:
    """
    统一 TTS 门面
    根据配置动态切换引擎
    """
    def __init__(self):
        self.config = global_config.get_system().presentation.tts
        self.clients = {
            "gpt-sovits": GPTSoVITSClient(),
            "edge-tts": EdgeTTSClientEngine(),
        }
        self.current_engine = self.config.engine
        logger.info(f"[TTS] 初始化完成. 默认引擎: {self.current_engine}")

    def switch_engine(self, engine_name: str):
        if engine_name in self.clients:
            self.current_engine = engine_name
            logger.info(f"[TTS] 引擎切换为: {engine_name}")
        else:
            logger.warning(f"[TTS] 未知引擎 {engine_name}，保持 {self.current_engine}")

    async def synthesize(self, text: str) -> Optional[Path]:
        client = self.clients.get(self.current_engine)
        if not client:
            logger.error(f"[TTS] 引擎 {self.current_engine} 未实现")
            return None
        return await client.synthesize(text)

    def play(self, audio_path: Path):
        client = self.clients.get(self.current_engine)
        if client:
            client.play(audio_path)
    
    def stop(self):
        for c in self.clients.values():
            c.stop()

# Export compatible alias
EdgeTTSClient = UnifiedTTSClient
