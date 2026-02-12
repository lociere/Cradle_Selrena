@echo off
cd /d "%~dp0.."

if not exist ".venv" (
    echo [X] Please run install.bat first!
    pause
    exit /b
)

:: 1. 显式激活虚拟环境
echo [1/4] Activating Virtual Environment (.venv)...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [X] Failed to activate virtual environment.
    pause
    exit /b
)

echo.
echo ===============================================
echo     Switching PyTorch to GPU (CUDA) Version
echo ===============================================

:: 2. 卸载旧版本
echo [2/4] Uninstalling current CPU version...
pip uninstall -y torch torchaudio torchvision funasr

:: 3. 安装 GPU 版本
:: 策略变更: Python 3.14 属于超前版本，我们需要使用 Nightly (预览版) 源
:: 这里的 URL 涵盖了最新的 CUDA 支持
echo [3/4] Installing GPU version...
echo     Downloading components...

pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu124

:: 4. 重新安装 FunASR
echo [4/4] Reinstalling FunASR...
pip install funasr

echo.
echo ===============================================
echo [V] GPU Environment Setup Complete!
echo ===============================================
echo Now you can run 'start.bat' to enjoy faster ASR.
pause