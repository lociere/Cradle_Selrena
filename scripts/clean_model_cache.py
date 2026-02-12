"""
scripts/clean_model_cache.py

用途：清理项目范围内的模型缓存与临时文件（安全模式），
- 删除 ProjectPath.DATA_CACHE/hub_sandbox（ModelScope/HF/Torch 沙箱）
- 清理 assets/models 中的临时下载残留（例如以 ._____temp 开头的目录）

用法：
    python scripts/clean_model_cache.py --full   # （可选）执行更激进的清理
"""
import shutil
from pathlib import Path
from cradle.utils.path import ProjectPath

def clean_cache(full: bool = False) -> list[Path]:
    removed = []
    # 1) 清理 hub_sandbox（ModelScope / HF 沙箱）
    hub_sandbox = ProjectPath.DATA_CACHE / "hub_sandbox"
    if hub_sandbox.exists():
        try:
            shutil.rmtree(hub_sandbox)
            removed.append(hub_sandbox)
        except Exception as e:
            print(f"Failed to remove {hub_sandbox}: {e}")

    # 2) 清理 assets/models 下的临时残留
    assets_models = ProjectPath.ASSETS_MODELS
    if assets_models.exists():
        for child in assets_models.iterdir():
            # 删除 ModelScope 临时目录（以 ._____temp 开头）
            if child.name.startswith('._____temp') or child.name.endswith('.tmp'):
                try:
                    shutil.rmtree(child)
                    removed.append(child)
                except Exception as e:
                    print(f"Failed to remove temp dir {child}: {e}")

            # 可选：彻底清理指定模型（full 模式）
            if full and child.is_dir():
                # 仅在 full 模式下删除已下载模型目录
                try:
                    shutil.rmtree(child)
                    removed.append(child)
                except Exception as e:
                    print(f"Failed to remove model dir {child}: {e}")

    return removed

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--full', action='store_true', help='删除 assets/models 下的所有模型目录（危险）')
    args = p.parse_args()

    removed = clean_cache(full=args.full)
    if removed:
        print('Removed:')
        for r in removed:
            print(' -', r)
    else:
        print('No cache/temp files found to remove.')
