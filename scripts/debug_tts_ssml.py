
import asyncio
import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"
OUTPUT_FILE_1 = "test_ssml_with_voice_arg.mp3"
OUTPUT_FILE_2 = "test_ssml_no_voice_arg.mp3"

SSML_TEXT = """<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN"><voice name="zh-CN-XiaoxiaoNeural"><mstts:express-as style="cheerful"><prosody rate="+12%" volume="+0%" pitch="+0Hz">你好，这是测试语音。</prosody></mstts:express-as></voice></speak>"""

async def run_tests():
    print("Testing SSML generation...")
    
    # Test 1: Passing voice argument
    print(f"Generating {OUTPUT_FILE_1} (with voice arg)...")
    try:
        comm = edge_tts.Communicate(text=SSML_TEXT, voice=VOICE)
        await comm.save(OUTPUT_FILE_1)
        print("Success 1")
    except Exception as e:
        print(f"Error 1: {e}")

    # Test 2: NOT passing voice argument (wrapper might need it?)
    # If edge-tts detects SSML, it might ignore voice, or we might need to extract it?
    # Actually edge-tts library usually Requires voice arg unless it parses it from SSML.
    # But if we pass it, does it break?
    
    print(f"Generating {OUTPUT_FILE_2} (parsing voice from SSML?)...")
    # Note: Communicate constructor signature is (text, voice=None, ...)
    # If we don't pass voice, and it's not detected, it might fail.
    try:
        comm = edge_tts.Communicate(text=SSML_TEXT) 
        await comm.save(OUTPUT_FILE_2)
        print("Success 2")
    except Exception as e:
        print(f"Error 2: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
