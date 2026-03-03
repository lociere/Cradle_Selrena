@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: [1] Environment Pre-Check
:: ================================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: ================================================================
:: [2] Virtual Environment Setup
:: ================================================================
set "VENV_DIR=.venv"
if not exist "%VENV_DIR%" (
    echo [Info] Creating virtual environment '%VENV_DIR%'...
    python -m venv %VENV_DIR%
)

echo [Info] Activating virtual environment...
call %VENV_DIR%\Scripts\activate

:: ================================================================
:: [3] Core Package Installation
:: ================================================================
echo [Info] Upgrading pip...
python -m pip install --upgrade pip setuptools wheel

echo [Info] Installing project dependencies from pyproject.toml...
:: Prefer pyproject.toml for modern dependency management
pip install -e .

:: ================================================================
:: [4] Hardware Acceleration (GPU) Patch
:: ================================================================
echo.
echo [Info] Applying GPU Acceleration Patches...
echo [Info] Installing llama-cpp-python (CUDA 12.4 Pre-built Wheel)...

:: Force reinstall llama-cpp-python from the cu124 index to ensure GPU support
pip install llama-cpp-python>=0.3.16 ^
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 ^
    --force-reinstall --no-cache-dir

:: Pin numpy to prevent numba conflicts (Audio module stability)
echo [Info] Pinning numpy version for audio compatibility...
pip install "numpy<2.4" soundfile

echo.
echo ========================================================
echo   [SUCCESS] Environment Setup Complete!
echo   You can now run 'scripts\start.bat' to launch Selrena.
echo ========================================================
pause
