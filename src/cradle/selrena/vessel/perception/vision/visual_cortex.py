import base64
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import aiofiles
import httpx

from cradle.schemas.configs.soul import SoulConfig
from cradle.utils.logger import logger

from ..base import BaseCortex, BaseNeuralSignal


@dataclass
class VisualSignal(BaseNeuralSignal):
    """视觉信号数据包"""
    image_base64: str
    media_type: str = "image/jpeg"
    original_url: str = ""


class VisualCortex(BaseCortex):
    """
    视觉皮层 (Visual Cortex)
    职责:
    1. 接收外界的视觉信号 (URL)
    2. “视网膜成像”: 将光信号转化为电信号 (Download -> Base64)
    3. 不再负责“理解”(Vision LLM)，只负责“传递”(Pass through)
    """

    def __init__(self, config: SoulConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        self._http_client = httpx.AsyncClient(
            verify=False, timeout=30.0, follow_redirects=True)
        logger.info(f"[VisualCortex] Retina Initialized.")

    async def cleanup(self):
        if self._http_client:
            await self._http_client.aclose()

    def has_signal(self, text: str) -> bool:
        """检测输入中是否包含视觉信号"""
        if not text:
            return False

        has_url = "http" in text or "file://" in text
        is_qq_link = "multimedia.nt.qq.com" in text or "c2cpicdw.qpic.cn" in text
        # QQ sometimes sends XML/JSON rich media snippets which we ignore for now
        # We focus on explicit image indicators
        has_tag = "[图片]" in text or "image" in text.lower(
        ) or "picture" in text.lower() or "【视觉输入】" in text

        return (has_url and has_tag) or is_qq_link

    async def process(self, text: str) -> Tuple[str, List[VisualSignal]]:
        """
        处理视觉信号
        Returns: (sanitized_text, List[VisualSignal])
        """
        urls = self._extract_urls(text)
        if not urls:
            return text, []

        logger.debug(f"[VisualCortex] Retina capturing {len(urls)} photons...")

        signals: List[VisualSignal] = []

        # 提取并转换所有图像
        # 考虑到 API Token 消耗和传输延迟，默认限制处理前 1 张，如有需要后续可提至配置
        target_urls = urls[:1]

        for url in target_urls:
            try:
                base64_data, media_type = await self._hydrate_image(url)
                if base64_data:
                    signals.append(VisualSignal(
                        image_base64=base64_data,
                        media_type=media_type,
                        original_url=url
                    ))
            except Exception as e:
                logger.error(
                    f"[VisualCortex] Failed to capture image {url}: {e}")

        # 清理文本中的 URL，用 [IMAGE] 占位符替代，方便下游对齐
        clean_text = text
        for url in urls:
            clean_text = clean_text.replace(url, "")  # 直接移除 URL

        clean_text = clean_text.replace("[图片]", "[IMAGE]").replace(
            "[image]", "[IMAGE]").replace("【视觉输入】", "[IMAGE]")

        # 去重多余的空白和无用的连续 [IMAGE] 标签
        clean_text = re.sub(r'(\[IMAGE\]\s*)+', '[IMAGE] ', clean_text)

        return clean_text.strip(), signals

    def _extract_urls(self, text: str) -> List[str]:
        # slightly better regex to avoid trailing ]
        urls = re.findall(r'(https?://[^\s,\]]+)', text)
        return urls

    async def _hydrate_image(self, url: str) -> Tuple[str, str]:
        """Download or read image and convert to base64. Returns (base64_str, media_type)"""
        import mimetypes

        if url.startswith("file://"):
            file_path = url.replace("file://", "")
            if os.name == 'nt' and file_path.startswith('/'):
                file_path = file_path[1:]

            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "image/jpeg"

            async with aiofiles.open(file_path, "rb") as f:
                data = await f.read()
                return base64.b64encode(data).decode('utf-8'), mime_type

        # HTTP
        try:
            resp = await self._http_client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "image/jpeg")
            return base64.b64encode(resp.content).decode('utf-8'), content_type
        except Exception as e:
            logger.error(f"[VisualCortex] Network error fetching image: {e}")
            raise e
