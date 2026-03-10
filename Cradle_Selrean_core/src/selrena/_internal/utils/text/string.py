# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)
MARKDOWN_FENCE_RE = re.compile(r"```(?:\w+)?\s*(.*?)\s*```", flags=re.DOTALL)
ACTION_BRACKET_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
EMOTION_TAG_RE = re.compile(
    r"\[(?:calm|happy|sad|angry|excited|emotion|fear|cute|[a-zA-Z_\-]{1,20}|[^\]]{1,20})\]",
    flags=re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
ASR_TAG_RE = re.compile(r"<\|.*?\|>")
LEADING_EMOTION_TAG_RE = re.compile(r"^\s*\[([a-zA-Z_\-]{1,32})\]\s*")


@dataclass(frozen=True)
class TextCleanOptions:
    remove_think_blocks: bool = True
    remove_markdown_fences: bool = False
    remove_action_descriptions: bool = True
    remove_emotion_tags: bool = True
    remove_html_tags: bool = False
    collapse_whitespace: bool = True
    preserve_newlines: bool = True


def clean_text(text: str, options: TextCleanOptions = TextCleanOptions()) -> str:
    if not text:
        return ""
    cleaned = text
    if options.remove_think_blocks:
        cleaned = THINK_BLOCK_RE.sub("", cleaned)
    if options.remove_markdown_fences:
        cleaned = MARKDOWN_FENCE_RE.sub(r"\1", cleaned)
    if options.remove_action_descriptions:
        cleaned = ACTION_BRACKET_RE.sub("", cleaned)
    if options.remove_emotion_tags:
        cleaned = EMOTION_TAG_RE.sub("", cleaned)
    if options.remove_html_tags:
        cleaned = HTML_TAG_RE.sub("", cleaned)
    if options.collapse_whitespace:
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        if options.preserve_newlines:
            cleaned = MULTI_SPACE_RE.sub(" ", cleaned)
            cleaned = MULTI_NEWLINE_RE.sub("\n\n", cleaned)
        else:
            cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def clean_for_tts(text: str) -> str:
    return clean_text(
        text,
        TextCleanOptions(
            remove_think_blocks=True,
            remove_markdown_fences=True,
            remove_action_descriptions=True,
            remove_emotion_tags=True,
            remove_html_tags=True,
            collapse_whitespace=True,
            preserve_newlines=False,
        ),
    )


def clean_asr_transcript(text: str) -> str:
    if not text:
        return ""
    cleaned = ASR_TAG_RE.sub("", text)
    return clean_text(
        cleaned,
        TextCleanOptions(
            remove_think_blocks=True,
            remove_markdown_fences=False,
            remove_action_descriptions=False,
            remove_emotion_tags=False,
            remove_html_tags=False,
            collapse_whitespace=True,
            preserve_newlines=True,
        ),
    )


def clean_for_dialogue(text: str) -> str:
    return clean_text(
        text,
        TextCleanOptions(
            remove_think_blocks=True,
            remove_markdown_fences=False,
            remove_action_descriptions=True,
            remove_emotion_tags=True,
            remove_html_tags=False,
            collapse_whitespace=True,
            preserve_newlines=True,
        ),
    )


def extract_emotion_and_clean_text(text: str) -> Tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", ""
    match = LEADING_EMOTION_TAG_RE.match(raw)
    if match:
        emotion = match.group(1)
        cleaned = raw[match.end() :].strip()
    else:
        emotion = ""
        cleaned = raw
    return cleaned, emotion


def extract_json_from_text(text: str) -> Union[Dict[str, Any], None]:
    """Attempt to parse a JSON object from the given text.
    Returns the object if successful, otherwise None."""
    try:
        return json.loads(text)
    except Exception:
        # brute-force search for first {...} block
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def truncate_text(text: str, max_len: int = 200) -> str:
    """Return text truncated to max_len characters."""
    if not isinstance(text, str):
        return text
    return text if len(text) <= max_len else text[:max_len]
