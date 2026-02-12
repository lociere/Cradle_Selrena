import os
import sys
import numpy as np
 # 已移除 soundfile 相关引用
from funasr import AutoModel

project_root = r"D:\elise\Cradle_Selrena"
wav_path = os.path.join(project_root, "logs", "debug_audio", "last_speech.wav")
model_identifier = "iic/SenseVoiceSmall"

if not os.path.exists(wav_path):
    print(f"File not found: {wav_path}")
    sys.exit(1)

print(f"Loading model: {model_identifier}")
# FunASR default cache is user home .cache
try:
    model = AutoModel(
        model=model_identifier,
        device="cuda",
        disable_update=True,
        log_level="ERROR"
    )
except Exception as e:
    print(f"Failed to load model: {e}")
    sys.exit(1)

print("-" * 30)
print(f"Testing file: {wav_path}")

# Test 1: File Path
print("\n[Test 1] Passing File Path directly...")
try:
    res = model.generate(input=wav_path, language="zh", use_itn=True, merge_vad=False)
    print(f"Output: {res}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Float32 Numpy
print("\n[Test 2] Passing Float32 Numpy Array...")
try:
    # 已移除 soundfile 相关用法
    # Verify shape
    print(f"Audio shape: {audio.shape}, min: {audio.min()}, max: {audio.max()}")
    
    res = model.generate(input=audio, language="zh", use_itn=True, merge_vad=False)
    print(f"Output: {res}")
except Exception as e:
    print(f"Error: {e}")
