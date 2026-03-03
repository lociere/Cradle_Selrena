import re
import html
from typing import Any, Dict, List, Optional, Tuple, Union

class NapcatMessageParser:
    """
    Napcat 消息解析器
    """
    
    @staticmethod
    def parse_cq_codes(raw_text: str) -> Dict[str, Any]:
        """
        Extract structured data from CQ Codes (like at, reply, face).
        Not just removal, but data extraction.
        """
        data = {
            "at": [],
            "reply": None,
            "face": [],
            "image": [],
            "video": [],
            "text": ""
        }
        
        # 1. Reply
        reply_match = re.search(r'\[CQ:reply,id=(\d+)\]', raw_text)
        if reply_match:
            data["reply"] = reply_match.group(1)
            raw_text = re.sub(r'\[CQ:reply,id=\d+\]', '', raw_text)
            
        # 2. At
        at_matches = re.finditer(r'\[CQ:at,qq=(\d+)\]', raw_text)
        for match in at_matches:
            data["at"].append(match.group(1))
        # Keep At text or remove? Usually remove or replace with '@123456 '
        # We replace with a space-padded marker to separate it from following text
        # But for Soul's prompt, raw ID is confusing. Replaced with generic @
        raw_text = re.sub(r'\[CQ:at,qq=\d+\]', ' @User ', raw_text)

        # 3. Image/Video
        img_matches = re.finditer(r'\[CQ:image,file=([^,]+).*?\]', raw_text)
        for match in img_matches:
            data["image"].append(match.group(1))
        # Replace image with Vision placeholder (handled in Cortex) or just remove
        raw_text = re.sub(r'\[CQ:image,[^\]]+\]', '[图片]', raw_text)

        # 4. Clean Text
        raw_text = NapcatMessageCleaner.cleanup_noise(raw_text)
        data["text"] = raw_text.strip()
        
        return data

    @staticmethod
    def normalize_message_chain(message_chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize a Napcat 'message' array into a unified structure.
         Handles: text, image, face, at, reply, forward, etc.
        """
        result = {
            "text": "",
            "images": [],
            "videos": [],
            "at_users": [],
            "reply_to": None,
            "raw_chain": message_chain
        }
        
        text_parts = []
        
        for segment in message_chain:
            type_ = segment.get("type")
            data = segment.get("data", {})
            
            if type_ == "text":
                text_parts.append(data.get("text", ""))
            elif type_ == "image":
                url = data.get("url") or data.get("file")
                if url:
                    result["images"].append(url)
            elif type_ == "video":
                url = data.get("url") or data.get("file")
                if url:
                    result["videos"].append(url)
            elif type_ == "at":
                qq = data.get("qq")
                if qq:
                    result["at_users"].append(qq)
                    # [Enhancement] Insert placeholder to keep position info
                    text_parts.append(f" [HQ:at,qq={qq}] ")
            elif type_ == "reply":
                result["reply_to"] = data.get("id")
            elif type_ == "face":
                # Convert face to text description if possible, or ignore
                pass
            elif type_ == "forward" or type_ == "node":
                # [Enhancement] Mark forward messages
                text_parts.append(" [转发/合并消息] ")
            
        result["text"] = NapcatMessageCleaner.cleanup_noise("".join(text_parts))
        return result


class NapcatMessageCleaner:
    """
    Napcat 消息清洗工具 (Refactored from Global Preprocessor)
    """

    @staticmethod
    def cleanup_noise(text: str) -> str:
        """
        Remove CQ Codes and specific placeholders.
        This logic is now encapsulated within Napcat module.
        """
        if not text:
            return ""

        # 1. 移除 CQ 码
        text = re.sub(r'\[CQ:[^\]]+\]', '', text)
        
        # 2. 移除特定占位符
        text = re.sub(r'\[(图片|动画表情|表情|视频|语音|回复)\]', '', text)
        
        # 3. 移除多媒体 URL
        text = NapcatMessageCleaner._cleanup_multimedia_urls(text)
        
        # 4. HTML Unescape
        text = html.unescape(text)

        return text.strip()

    @staticmethod
    def _cleanup_multimedia_urls(text: str) -> str:
        """Internal: cleanup腾讯多媒体 URLs"""
        if not text:
            return ""
        patterns = [
            r'https?://multimedia\.nt\.qq\.com\.cn/[^\s]+',
            r'https?://(c2cpicdw\.qpic\.cn|groups-pic\.qlogo\.cn|gchat\.qpic\.cn)/[^\s]+'
        ]
        for p in patterns:
            text = re.sub(p, '', text)
        return text
