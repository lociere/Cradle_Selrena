@echo off
setlocal

echo ========================================================
echo       Cradle_Selrena 一键全能部署 (All-in-One)
echo ========================================================

:: ---------------------------------------------------
:: 1. 检测并安装 FFmpeg (多媒体核心)
:: ---------------------------------------------------
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] FFmpeg 未检测到，尝试通过 Winget 自动安装...
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    echo [V] FFmpeg 安装指令已执行
) else (
    echo [V] FFmpeg 已就绪
)

:: ---------------------------------------------------
:: 2. 智能创建虚拟环境 (优先锁定 Python 3.12)
:: ---------------------------------------------------
if exist ".venv" (
    echo [V] 虚拟环境 .venv 已存在，准备进行增量更新...
) else (
    echo [!] 正在创建全新的虚拟环境...
    
    :: 尝试寻找 Python 3.12 (兼容性最佳版本)
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        echo [V] 捕获到 Python 3.12，正在创建环境...
        py -3.12 -m venv .venv
    ) else (
        echo [!] 未找到 Py3.12，使用系统默认 Python...
        echo     (警告: 如果是 Python 3.14 可能会导致 PyTorch 安装失败)
        python -m venv .venv
    )
    
    if not exist ".venv" (
        echo [X] 虚拟环境创建失败！请检查 Python 是否正确安装。
        pause
        exit /b 1
    )
)

:: ---------------------------------------------------
:: 3. 激活环境 & 注入 GPU 核动力
:: ---------------------------------------------------
echo [!] 正在激活环境...
call .venv\Scripts\activate.bat

echo [!] 正在部署驱动引擎 (此步耗时较长)...
echo     目标: PyTorch CUDA 12.4 (适配 RTX 显卡)

:: 核心操作：先卸载可能存留的 CPU 版，再安装 GPU 版
pip uninstall -y torch torchvision torchaudio funasr
python -m pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

:: ---------------------------------------------------
:: 4. 安装应用层依赖
:: ---------------------------------------------------
echo [!] 正在安装 Cradle_Selrena 核心组件...
:: 安装项目依赖 (Editable模式)
pip install -e .
:: 补全所有依赖，包括记忆模块和多媒体库
pip install -r requirements.txt
pip install chromadb sentence-transformers transformers huggingface-hub llama-cpp-python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install edge-tts funasr sounddevice webrtcvad-wheels

:: ---------------------------------------------------
:: 5. 系统初始化
:: ---------------------------------------------------
echo [!] 初始化数据仓储...
set PYTHONPATH=src
python -c "from cradle.utils.path import ProjectPath; ProjectPath.ensure_dirs(); print('System initialized.')"

echo.
echo ========================================================
echo           🎉 部署完成！Selrena 已就绪
echo ========================================================
echo  使用方法: 双击 start.bat 即可唤醒。
echo.
pause