from llama_cpp import Llama
import os

model_path = r"D:\elise\Cradle_Selrena\assets\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"
n_gpu_layers = -1
n_ctx = 4096  # Match production config

print(f"Attempting to load model from: {model_path}")
print(f"n_gpu_layers: {n_gpu_layers}")
print(f"n_ctx: {n_ctx}")

if not os.path.exists(model_path):
    print("Error: File does not exist!")
    exit(1)

try:
    llm = Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
        verbose=True
    )
    print("Success! Model loaded.")
except Exception as e:
    print(f"Failed to load model: {e}")
