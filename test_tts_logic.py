
import re
import xml.sax.saxutils

def test_cleaning_and_ssml():
    text_input = "[calm]你刚才叫我什么？是月见哦。 [happy] 至于吃饭……"
    
    # 模拟 _parse_emotion 的逻辑
    print(f"原始文本: '{text_input}'")
    
    text = text_input.strip()
    emotion = "chat" # 默认为 chat 而不是 calm，或者映射 calm -> chat
    style_map = {
        "happy": "cheerful",
        "sad": "sad",
        "calm": "chat",
    }
    
    # 1. 尝试提取情感 (寻找第一个匹配的有效标签)
    match = re.search(r"\[(\w+)\]", text)
    if match:
        tag = match.group(1).lower()
        if tag in style_map:
            emotion = style_map[tag] # 这里逻辑有点问题，得到的是 style name
            print(f"检测到情感标签: {tag} -> style: {emotion}")
    
    # 2. 清洗文本
    # 移除所有 [...] 格式的标签
    clean_text = re.sub(r"\[\w+\]", "", text)
    clean_text = clean_text.strip()
    
    print(f"清洗后文本: '{clean_text}'")
    
    # 模拟 SSML 生成
    safe_text = xml.sax.saxutils.escape(clean_text)
    
    # 注意：这里的缩进可能会导致问题，我们要测试生成的字符串是否带有前导空白
    ssml_text = f"""
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='zh-CN'>
    <voice name='zh-CN-XiaoxiaoNeural'>
        <mstts:express-as style='{emotion}'>
            <prosody rate='+0%' volume='+0%' pitch='+0Hz'>
                {safe_text}
            </prosody>
        </mstts:express-as>
    </voice>
</speak>
""".strip()

    print("\n--- 生成的 SSML ---")
    print(f"'{ssml_text}'")
    print("-------------------")
    
    if ssml_text.startswith("<speak"):
        print("检查通过: SSML 以 <speak 开头")
    else:
        print("检查失败: SSML 包含前导字符")

if __name__ == "__main__":
    test_cleaning_and_ssml()
