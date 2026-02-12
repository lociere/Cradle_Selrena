from modelscope.hub.api import HubApi

api = HubApi()
repo_id = "Qwen/Qwen2.5-7B-Instruct-GGUF"

try:
    print(f"Listing files in {repo_id}...")
    files = api.get_model_files(model_id=repo_id)
    for f in files:
        print(f)
except Exception as e:
    print(f"Error: {e}")
