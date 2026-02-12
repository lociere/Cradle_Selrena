import os
import sys
import argparse
import shutil
from typing import Dict, Any, Optional

# ==========================================
# 📦 资产注册表 (Asset Manifest)
# 将所有需要下载的外部资源在这里注册
# ==========================================
ASSETS = {
    # --- 核心大脑 (LLM) ---
    "llm": {
        "type": "file", # 单文件模式
        "description": "🧠 大脑 (LLM) - Qwen2.5 GGUF",
        "target_dir": "assets/models",
        "default_variant": "Q4_K_M",
        "variants": {
            "Q4_K_M": {
                "description": "推荐: 平衡 (4.7GB)",
                "ms_repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
                "ms_file": "qwen2.5-7b-instruct-q4_k_m.gguf", # ModelScope 小写
                "hf_repo": "bartowski/Qwen2.5-7B-Instruct-GGUF",
                "hf_file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
                "local_name": "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
            },
            "Q3_K_M": {
                "description": "极速: 6GB显卡专用 (3.8GB)",
                "ms_repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
                "ms_file": "qwen2.5-7b-instruct-q3_k_m.gguf",
                "hf_repo": "bartowski/Qwen2.5-7B-Instruct-GGUF",
                "hf_file": "Qwen2.5-7B-Instruct-Q3_K_M.gguf",
                "local_name": "Qwen2.5-7B-Instruct-Q3_K_M.gguf"
            }
        }
    },
    
    # --- 听觉中枢 (ASR) ---
    "asr": {
        "type": "folder", # 文件夹快照模式
        "description": "👂 耳朵 (ASR) - SenseVoiceSmall",
        "target_dir": "assets/models",
        "default_variant": "default",
        "variants": {
            "default": {
                "description": "多语言高精度语音识别",
                "ms_repo": "iic/SenseVoiceSmall",
                "hf_repo": "FunAudioLLM/SenseVoiceSmall",
                "local_name": "SenseVoiceSmall" # 最终文件夹名
            }
        }
    },

    # --- 记忆海马体 (Embedding) ---
    "embedding": {
        "type": "folder",
        "description": "🧠 记忆索引 (Embedding) - CPU Optimized",
        "target_dir": "assets/models",
        "default_variant": "m3e_small",
        "variants": {
            "m3e_small": {
                "description": "极速中文语义向量 (CPU Friendly)",
                "ms_repo": "Jerry0/m3e-small",
                "hf_repo": "moka-ai/m3e-small",
                "local_name": "m3e-small"
            },
            "bge_small": {
                "description": "高精度中文向量 (BAAI BGE)",
                "ms_repo": "AI-ModelScope/bge-small-zh-v1.5",
                "hf_repo": "BAAI/bge-small-zh-v1.5",
                "local_name": "bge-small-zh-v1.5"
            }
        }
    }
    # 未来可扩展: "tts", "vision", "avatar_assets" ...
}

# ==========================================
# 🛠️ 核心逻辑
# ==========================================

from cradle.utils.path import ProjectPath


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def download_file_from_ms(repo_id, filename, target_path):
    """从 ModelScope 下载单文件"""
    print(f"   [ModelScope] 正在下载文件: {filename} ...")
    try:
        from modelscope.hub.file_download import model_file_download
        cached_path = model_file_download(model_id=repo_id, file_path=filename)
        print(f"   [Move] 部署到: {target_path}")
        shutil.copy2(cached_path, target_path)
        return True
    except ImportError:
        print("   ⚠️ 未安装 modelscope 库")
        return False
    except Exception as e:
        print(f"   ❌ ModelScope 下载失败: {e}")
        return False

def download_folder_from_ms(repo_id, target_path):
    """从 ModelScope 下载文件夹 (Snapshot)"""
    print(f"   [ModelScope] 正在下载模型仓库: {repo_id} ...")
    try:
        from modelscope.hub.snapshot_download import snapshot_download
        # 下载到缓存
        cached_path = snapshot_download(model_id=repo_id)
        
        # 如果目标文件夹已存在，先清空（防止旧文件残留干扰）
        if os.path.exists(target_path):
            print(f"   [Clean] 清理旧目录: {target_path}")
            shutil.rmtree(target_path)
            
        print(f"   [Move] 部署到: {target_path}")
        shutil.copytree(cached_path, target_path)
        return True
    except ImportError:
        print("   ⚠️ 未安装 modelscope 库")
        return False
    except Exception as e:
        print(f"   ❌ ModelScope 下载失败: {e}")
        return False

def download_file_from_hf(repo_id, filename, target_path):
    """从 HuggingFace 镜像下载单文件"""
    print(f"   [HuggingFace] 正在尝试镜像下载: {filename} ...")
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    try:
        from huggingface_hub import hf_hub_download
        # hf_hub_download 可以直接下载到 local_dir
        target_dir = os.path.dirname(target_path)
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=target_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )
        return True
    except ImportError:
        print("   ⚠️ 未安装 huggingface_hub 库")
        return False
    except Exception as e:
        print(f"   ❌ HuggingFace 下载失败: {e}")
        return False

def download_folder_from_hf(repo_id, target_path):
    """从 HuggingFace 镜像下载文件夹"""
    print(f"   [HuggingFace] 正在尝试镜像下载仓库: {repo_id} ...")
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=repo_id,
            local_dir=target_path,
            local_dir_use_symlinks=False,
            resume_download=True
        )
        return True
    except Exception as e:
        print(f"   ❌ HuggingFace 下载失败: {e}")
        return False

def process_asset(key, config, args):
    """处理单个资产的下载逻辑"""
    print(f"\n🚀 正在检查模块: [{key}] {config['description']}")
    
    # 确定具体变体 (Variant)
    variant_key = args.variant if (key == "llm" and args.variant) else config["default_variant"]
    if variant_key not in config["variants"]:
        print(f"   ⚠️ 变体 '{variant_key}' 不存在，回退到默认: {config['default_variant']}")
        variant_key = config["default_variant"]
    
    info = config["variants"][variant_key]
    print(f"   📋 选定版本: {variant_key} ({info['description']})")
    
    # 准备路径（使用 ProjectPath 工具）
    target_parent = str(ProjectPath.ASSETS_MODELS)
    ensure_dir(target_parent)

    target_path = str(ProjectPath.get_model_path(info["local_name"]))

    # 检查是否存在
    exists = os.path.exists(target_path)
    if exists and not args.force:
        print(f"   ✅ 资源已就绪: {target_path}")
        return
    
    if args.force:
        print("   FORCE 模式开启，将覆盖现有文件。")

    # 开始下载 (策略: MS -> HF)
    success = False
    
    # 1. 尝试 ModelScope
    if config["type"] == "file":
        success = download_file_from_ms(info["ms_repo"], info["ms_file"], target_path)
    else:
        success = download_folder_from_ms(info["ms_repo"], target_path)
        
    if success:
        print(f"   🎉 [{key}] 部署完成!")
        return

    # 2. 尝试 HuggingFace
    print("   ⚠️ 首选源失败，尝试备用源...")
    if config["type"] == "file":
        success = download_file_from_hf(info["hf_repo"], info["hf_file"], target_path)
    else:
        success = download_folder_from_hf(info["hf_repo"], target_path)
        
    if success:
        print(f"   🎉 [{key}] 部署完成!")
    else:
        print(f"   💀 [{key}] 所有源下载均失败。")
        print("   请检查网络连接或手动安装依赖: pip install modelscope huggingface_hub")

def main():
    parser = argparse.ArgumentParser(description="Cradle Selrena 统一资产管理器")
    
    # 主命令：选择要下载的模块
    parser.add_argument("module", nargs="?", default="all", 
                        choices=["all"] + list(ASSETS.keys()),
                        help="选择要下载的模块 (默认: all)")
    
    # 选项
    parser.add_argument("--variant", type=str, help="指定变体 (仅对 LLM 有效, e.g. Q3_K_M)")
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    
    args = parser.parse_args()
    
    title = "Cradle Asset Manager"
    print(f"{'='*len(title)}\n{title}\n{'='*len(title)}")
    
    if args.module == "all":
        targets = ASSETS.keys()
    else:
        targets = [args.module]
        
    for key in targets:
        process_asset(key, ASSETS[key], args)
        
    print("\n✅ 所有任务处理完毕。")

if __name__ == "__main__":
    main()
