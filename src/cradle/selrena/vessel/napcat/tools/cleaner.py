"""
Napcat 消息清洗器。

负责清理 CQ 码、多媒体 URL、HTML 转义等文本预处理任务。
"""

import re
import html
from typing import Any, Dict, List, Optional, Tuple, Union


class NapcatMessageCleaner:
    """
    Napcat 消息清洗工具类。
    
    职责：
    1. 移除 CQ 码（OneBot 协议标记）
    2. 清理多媒体 URL
    3. HTML 转义处理
    4. 移除特定占位符
    """

    @staticmethod
    def cleanup_noise(text: str) -> str:
        """
        移除 CQ 码和特定占位符，清理文本噪声。
        
        Args:
            text: 原始文本（可能包含 CQ 码、URL 等）
            
        Returns:
            清理后的纯文本
        """
        if not text:
            return ""

        # 1. 移除 CQ 码
        text = re.sub(r'\[CQ:[^\]]+\]', '', text)
        
        # 2. 移除特定占位符
        text = re.sub(r'\[(图片 | 动画表情 | 表情 | 视频 | 语音 | 回复)\]', '', text)
        
        # 3. 移除多媒体 URL
        text = NapcatMessageCleaner._cleanup_multimedia_urls(text)
        
        # 4. HTML Unescape
        text = html.unescape(text)

        return text.strip()

    @staticmethod
    def _cleanup_multimedia_urls(text: str) -> str:
        """
        清理腾讯多媒体 URLs（图片、视频等）。
        
        Args:
            text: 可能包含 URL 的文本
            
        Returns:
            移除 URL 后的文本
        """
        if not text:
            return ""
            
        patterns = [
            r'https?://multimedia\.nt\.qq\.com\.cn/[^\s]+',
            r'https?://(c2cpicdw\.qpic\.cn|groups-pic\.qlogo\.cn|gchat\.qpic\.cn)/[^\s]+'
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text)
            
        return text
