import sys
import subprocess
import platform
import os
import argparse
import shutil

# ================= Configuration =================
# 核心依赖 (Core): 系统运行的基础，必须安装
CORE_REQUIREMENTS = [
    "pydantic>=2.0",
    "python-dotenv",
    "pyyaml",
    "loguru",
    "numpy",
    "requests",
    "pillow",
    "pyautogui",  # 视觉感知/操作
]

# AI 引擎 (Intelligence): 涉及 PyTorch, ModelScope, LLM
# 注意：torch 和 llama-cpp-python 会在脚本中特殊处理
AI_REQUIREMENTS = [
    "openai>=1.0",
    "langchain",
    "langgraph",
    "modelscope",
    "funasr",          # 语音识别
    "sounddevice",     # 音频输入输出
    # "soundfile",  # 已移除
    "scipy",
    "chromadb",             # 向量数据库 (Project Mnemosyne)
    "sentence-transformers" # CPU Embedding (Project Mnemosyne)
]

# 用户界面 (GUI): 可选
GUI_REQUIREMENTS = [
    "PySide6",
]

# 开发工具 (Dev): 可选，用于格式化、测试等
DEV_REQUIREMENTS = [
    "black",
    "pytest",
    "huggingface_hub", # 用于备用下载
]

# 镜像源 (Mirror)
PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"

# ================= Helpers =================

def run_pip(args, description):
    """运行 pip 命令"""
    print(f"📦 [Setup] {description}...")
    cmd = [sys.executable, "-m", "pip", "install", "-i", PIP_INDEX_URL] + args
    try:
        subprocess.check_call(cmd)
        print(f"✅ {description} 完成.\n")
    except subprocess.CalledProcessError:
        print(f"❌ {description} 失败!")
        # 核心组件失败直接退出
        if "llama-cpp-python" in str(args) or "torch" in str(args):
            print("   这是一个关键组件，安装无法继续。")
            sys.exit(1)

def check_nvidia_gpu():
    """简单的 NVIDIA GPU 检测"""
    try:
        # 方法1: 尝试调用 nvidia-smi
        subprocess.check_output("nvidia-smi")
        print("✅ 检测到 NVIDIA GPU (通过 nvidia-smi)")
        return True
    except:
        pass
    
    # 可以在这里添加更多检测逻辑
    print("⚠️ 未检测到 nvidia-smi，将假定无 NVIDIA GPU（或驱动未配置）。")
    return False

def check_cuda_compiler():
    """检测 nvcc"""
    try:
        subprocess.check_output(["nvcc", "--version"])
        print("✅ 检测到 CUDA Compiler (nvcc)")
        return True
    except:
        print("⚠️ 未检测到 nvcc。如果这是一个 NVIDIA 环境，建议安装 CUDA Toolkit 以获得最佳性能。")
        return False

# ================= Main Tasks =================

def install_torch(has_gpu):
    """安装 PyTorch"""
    if has_gpu:
        print("🚀 正在为您安装 GPU 版 PyTorch (CUDA 12.4)...")
        # 直接指定 pytorch.org 的 index 可能比较慢，但它是最稳的
        # 这里我们使用 pip 的 --extra-index-url 配合清华源
        # 针对 CUDA 12.4
        run_pip(
            ["torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"],
            "安装 PyTorch (CUDA 12.4)"
        )
    else:
        print("🐢 正在为您安装 CPU 版 PyTorch...")
        run_pip(["torch", "torchvision", "torchaudio"], "安装 PyTorch (CPU)")

def install_llama_cpp(has_gpu, cuda_version="cu124"):
    """安装 llama-cpp-python"""
    pkg_name = "llama-cpp-python"
    
    # 先尝试卸载，避免版本冲突
    subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", pkg_name])

    if has_gpu:
        # 必须检查 nvcc，否则 gpu 编译会失败，或者使用预编译 wheels
        print(f"🚀 正在安装 {pkg_name} (GPU/CUDA)...")
        
        # 使用 abetlen 的预编译轮子，这是最稳健的方法，避免本地编译环境问题
        wheel_url = f"https://abetlen.github.io/llama-cpp-python/whl/{cuda_version}"
        
        # 强制重新安装，不安装依赖（依赖由我们自己控制）
        cmd = [
            sys.executable, "-m", "pip", "install", pkg_name,
            "--force-reinstall",
            "--no-deps",
            "--extra-index-url", wheel_url
        ]
        print(f"   Command: {' '.join(cmd)}")
        try:
            subprocess.check_call(cmd)
            print(f"✅ {pkg_name} (GPU) 安装完成.\n")
        except subprocess.CalledProcessError:
            print(f"❌ {pkg_name} (GPU) 安装失败。尝试回退到源码编译模式...")
            # 回退策略：设置 CMAKE 参数从源码安装
            env = os.environ.copy()
            env["CMAKE_ARGS"] = "-DGGML_CUDA=on"
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg_name, "-i", PIP_INDEX_URL],
                env=env
            )
    else:
        print(f"🐢 正在安装 {pkg_name} (CPU Mode)...")
        run_pip([pkg_name], f"安装 {pkg_name}")

def main():
    parser = argparse.ArgumentParser(description="Cradle Selrena 环境部署脚本")
    
    # 选项开关
    parser.add_argument("--cpu", action="store_true", help="强制使用 CPU 模式 (不安装 CUDA 相关库)")
    parser.add_argument("--no-gui", action="store_true", help="跳过 GUI 库 (PySide6) 安装")
    parser.add_argument("--dev", action="store_true", help="安装开发工具 (pytest, black, etc.)")
    parser.add_argument("--upgrade", action="store_true", help="升级所有包")
    
    args = parser.parse_args()

    print("==================================================")
    print(" 🛠️  Cradle Selrena 环境部署向导")
    print("==================================================")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.system()} {platform.release()}")
    
    # 1. 硬件检测
    has_nvidia = False
    if not args.cpu:
        has_nvidia = check_nvidia_gpu()
        if has_nvidia:
            check_cuda_compiler() # 只是给个提示
    else:
        print("⚠️ 用户强制指定 --cpu，跳过 GPU 检测。")

    # 2. 升级 pip
    subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-i", PIP_INDEX_URL])

    # 3. 安装 PyTorch
    install_torch(has_nvidia)

    # 4. 安装 llama-cpp-python (最关键的 LLM 引擎)
    # 只有在 Windows + Nvidia 环境下，我们默认使用 cu124 轮子
    # 其他环境可能需要调整逻辑，这里针对您的 Windows 环境优化
    install_llama_cpp(has_nvidia, cuda_version="cu124")

    # 5. 安装核心依赖
    run_pip(CORE_REQUIREMENTS, "安装核心依赖 (Core)")

    # 6. 安装 AI 依赖
    run_pip(AI_REQUIREMENTS, "安装 AI/语音组件")

    # 7. 可选组件
    if not args.no_gui:
        run_pip(GUI_REQUIREMENTS, "安装 GUI 组件 (PySide6)")
    else:
        print("⏭️  跳过 GUI 组件。")

    if args.dev:
        run_pip(DEV_REQUIREMENTS, "安装开发工具")
    
    print("==================================================")
    print(" 🎉 环境部署完成！")
    print("==================================================")
    print("下一步建议：")
    print("1. 运行下载脚本: python scripts/download_model.py")
    print("2. 启动系统:     python src/cradle/main.py")

if __name__ == "__main__":
    main()
