import re
import json
from typing import Optional, Dict, List, Any, Union

def clean_llm_response(text: str) -> str:
    '''
    清洗 LLM 返回的文本
    移除 <think>...</think> 思维链内容
    '''
    if not text:
        return ""
        
    # 1. 移除思维链 (DeepSeek R1 等推理模型)
    # flag=re.DOTALL 让 . 匹配换行符
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    return text.strip()

def _extract_bland_json(text: str) -> Optional[str]:
    '''
    辅助函数：通过堆栈拘束寻找第一个完整的json对象/数组字符串
    '''
    stack = []
    start_idx = -1

    # 遍历寻找第一个开括号以及对应的必括号
    for i, char in enumerate(text):
        if char in '{[':
            if not stack:
                start_idx = i   # 记录起始位置
            stack.append(char)
        elif char in '}]':
            if not stack:
                continue    # 没有开括号前的闭括号，忽略

            # 检查括号是否匹配
            last = stack[-1]
            if (last == '{' and char == '}') or (last == '[' and char == ']'):
                stack.pop()
                # 堆栈空了，说睦找到了一个完整的闭环
                if not stack:
                    return text[start_idx : i + 1]
                else:
                    # 括号不匹配（可能是格式错误的 JSON），重置或继续
                    # 这里简单处理：不做严苛校验，仅仅依靠计数
                    # 实际情况中，JSON内部字符串里可能有括号，需要更复杂的解析
                    # 但对于 LLM 提取，通常只要匹配最外层括号对即可
                    pass

    return None # 如果找不到，返回None
                

def extract_json_from_text(text: str) -> Optional[Union[Dict[str, Any], List[Any], Any]]:
    '''
    从乱糟糟的文本中提取并解析 JSON
    1.优先提取 ```json
    2.其次尝试寻找第一个完整之和的{}或[]结构
    '''
    text = clean_llm_response(text)
    
    # 1. Markdown 代码块
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        block_text = json_match.group(1)
        try:
            return json.loads(block_text)
        except json.JSONDecodeError:
            # 如果代码块里都不是合法JSON，那可能格式有误，继续尝试全文搜索
            pass

    # 2. 括号记数法提取
    candidate = _extract_bland_json(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    
    # 3. 原始暴力尝试
    # 有时候 LLM 给出的 JSON 并不完整或有转义问题，尝试找最大范围再碰碰运气
    try:
        start = text.find('{')
        end = text.find('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
    except:
        pass

    return None


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断长文本用于日志显示"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix


def sanitize_text(text: str) -> str:
    """
    清洗文本中的情绪标签、括号动作描述等，适用于终端输出、TTS、日志等场景。
    - 移除各种括号内的动作描述：()、（）、【】、*...* 等
    - 移除常见情绪标签：[calm][happy][sad][angry][excited][emotion] 及其他方括号内容
    返回清洗后的文本（会做 strip）。
    """
    if not text:
        return ""
    # 移除括号动作描述
    text = re.sub(r"[\（\(\【\*].*?[\）\)\】\*]", "", text)
    # 移除方括号中常见情绪标签或任意短标签
    text = re.sub(r"\[(?:calm|happy|sad|angry|excited|emotion|[^\]]{1,20})\]", "", text, flags=re.IGNORECASE)
    return text.strip()
