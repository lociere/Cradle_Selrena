import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

THINK_BLOCK_RE = re.compile(r'<think>.*?</think>',
                            flags=re.DOTALL | re.IGNORECASE)
MARKDOWN_FENCE_RE = re.compile(r'```(?:\w+)?\s*(.*?)\s*```', flags=re.DOTALL)
ACTION_BRACKET_RE = re.compile(r"[\?\(\?\*].*?[\?\)\?\*]")
EMOTION_TAG_RE = re.compile(
    r"\[(?:calm|happy|sad|angry|excited|emotion|fear|cute|[a-zA-Z_\-]{1,20}|[^\]]{1,20})\]",
    flags=re.IGNORECASE
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
    """
    ??????????
    ??? LLM ???TTS ???UI ???????
    """
    if not text:
        return ""

    cleaned = text

    if options.remove_think_blocks:
        cleaned = THINK_BLOCK_RE.sub('', cleaned)

    if options.remove_markdown_fences:
        cleaned = MARKDOWN_FENCE_RE.sub(r'\1', cleaned)

    if options.remove_action_descriptions:
        cleaned = ACTION_BRACKET_RE.sub('', cleaned)

    if options.remove_emotion_tags:
        cleaned = EMOTION_TAG_RE.sub('', cleaned)

    if options.remove_html_tags:
        cleaned = HTML_TAG_RE.sub('', cleaned)

    if options.collapse_whitespace:
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        if options.preserve_newlines:
            cleaned = MULTI_SPACE_RE.sub(' ', cleaned)
            cleaned = MULTI_NEWLINE_RE.sub('\n\n', cleaned)
        else:
            cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned.strip()


def clean_for_tts(text: str) -> str:
    """TTS ?????????????????????"""
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
    """?? ASR ????????????"""
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
    """?????????????/????????????"""
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
    """?????????????????????/?????"""
    raw = (text or "").strip()
    if not raw:
        return "", "neutral"

    detected_emotion = "neutral"
    while True:
        match = LEADING_EMOTION_TAG_RE.match(raw)
        if not match:
            break
        detected_emotion = match.group(1).lower()
        raw = raw[match.end():].lstrip()

    cleaned = clean_for_dialogue(raw)
    if not cleaned:
        cleaned = clean_for_dialogue(text)

    return cleaned, detected_emotion


def _extract_balanced_json(text: str) -> Optional[str]:
    '''
    ???????????????????json??/?????
    '''
    stack = []
    start_idx = -1

    # ??????????????????
    for i, char in enumerate(text):
        if char in '{[':
            if not stack:
                start_idx = i   # ??????
            stack.append(char)
        elif char in '}]':
            if not stack:
                continue    # ?????????????

            # ????????
            last = stack[-1]
            if (last == '{' and char == '}') or (last == '[' and char == ']'):
                stack.pop()
                # ?????????????????
                if not stack:
                    return text[start_idx: i + 1]
                else:
                    pass

    return None  # ????????None


def _try_parse_json(text: str) -> Optional[Union[Dict[str, Any], List[Any], Any]]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def extract_json_from_text(text: str) -> Optional[Union[Dict[str, Any], List[Any], Any]]:
    '''
    ????????????? JSON
    1.???? ```json
    2.??????????????{}?[]??
    '''
    text = clean_text(
        text,
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

    # 1. Markdown ???
    json_match = MARKDOWN_FENCE_RE.search(text)
    if json_match:
        block_text = json_match.group(1)
        parsed = _try_parse_json(block_text)
        if parsed is not None:
            return parsed

    # 2. ???????
    candidate = _extract_balanced_json(text)
    if candidate:
        parsed = _try_parse_json(candidate)
        if parsed is not None:
            return parsed

    # 3. ??????
    # ??? LLM ??? JSON ???????????????????????
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        parsed = _try_parse_json(text[start:end+1])
        if parsed is not None:
            return parsed

    return None


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """???????????"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix
