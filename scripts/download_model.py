"""
scripts/download_model.py
------------------------
显式下载模型到项目 `assets/models/`，用于离线部署前预抓取。
用法:
    python scripts/download_model.py moka-ai/m3e-small
"""
import sys
from cradle.core.model_manager import global_model_manager


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/download_model.py <model-id-or-name>")
        sys.exit(1)

    model_id = sys.argv[1]
    print(f"Downloading model: {model_id}")
    try:
        path = global_model_manager.resolve_model_path(model_id, auto_download=True)
        print(f"Model available at: {path}")
    except Exception as e:
        print(f"Failed to download/resolve model: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()
