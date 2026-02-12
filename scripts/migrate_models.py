import os
import shutil
from pathlib import Path

def migrate_models():
    """
    迁移默认缓存目录中的模型到项目统一管理目录
    """
    user_home = Path.home()
    project_root = Path(__file__).resolve().parents[1]  # scripts/ -> root
    
    # 目标目录
    target_root = project_root / "data" / "cache" / "hub"
    target_root.mkdir(parents=True, exist_ok=True)
    
    # 定义迁移映射关系 (Source -> Destination)
    migrations = {
        # ModelScope
        user_home / ".cache" / "modelscope": target_root / "modelscope",
        user_home / ".modelscope": target_root / "modelscope",
        
        # HuggingFace
        user_home / ".cache" / "huggingface": target_root / "huggingface",
        
        # Torch
        user_home / ".cache" / "torch": target_root / "torch",
    }
    
    print(f"🔄 开始扫描默认模型缓存... (目标: {target_root})")
    
    migrated_count = 0
    
    for src, dst in migrations.items():
        if src.exists() and any(src.iterdir()): # 存在且非空
            print(f"\n📦 发现现有缓存: {src}")
            if not dst.exists():
                dst.mkdir(parents=True, exist_ok=True)
            
            # 移动内容
            try:
                # 遍历源目录下的顶层项目进行移动，而不是直接移动根目录
                # 这样可以将 .modelscope 和 .cache/modelscope 合并
                for item in src.iterdir():
                    dst_item = dst / item.name
                    if dst_item.exists():
                        print(f"   ⚠️  跳过已存在项: {item.name}")
                        continue
                        
                    print(f"   🚀 正在移动: {item.name} -> {dst_item}")
                    shutil.move(str(item), str(dst_item))
                    migrated_count += 1
                
                # 尝试清理空的源目录 (可选)
                try:
                    src.rmdir()
                    print(f"   ✅ 清理空源目录: {src}")
                except OSError:
                    pass
                    
            except Exception as e:
                print(f"   ❌ 移动失败: {e}")
        else:
            # print(f"   ⚪ 未找到或为空: {src}")
            pass
            
    if migrated_count > 0:
        print(f"\n✨ 迁移完成! 共移动 {migrated_count} 个项目。")
    else:
        print("\n🍵 未发现默认路径下的模型文件，目前环境很干净。")
        print("   (不用担心，下次加载模型时会自动下载到新目录)")

    # 另外检查 assets/models
    local_models = project_root / "assets" / "models"
    if local_models.exists() and any(local_models.iterdir()):
         print(f"\n📂 assets/models 中已有本地文件 (这些不需要移动，通过 Config 直接引用即可):")
         for item in local_models.iterdir():
             print(f"   - {item.name}")

if __name__ == "__main__":
    migrate_models()
