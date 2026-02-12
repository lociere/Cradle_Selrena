import os
from llama_cpp import Llama

model_path = r"D:\elise\Cradle_Selrena\assets\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"

print(f"Checking file existence: {os.path.exists(model_path)}")
print(f"File size: {os.path.getsize(model_path) if os.path.exists(model_path) else 'N/A'}")

try:
    print("Attempting to load model...")
    llm = Llama(
        model_path=model_path,
        n_gpu_layers=-1, # Try with GPU first
        verbose=True
    )
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    
    try:
        print("Retrying with CPU only (n_gpu_layers=0)...")
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=0,
            verbose=True
        )
        print("Model loaded on CPU successfully!")
    except Exception as e_cpu:
        print(f"Error loading model on CPU: {e_cpu}")
