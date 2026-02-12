@echo off
title Cradle_Selrena Console

:: 检查虚拟环境
if not exist ".venv" (
    echo [X] 未找到虚拟环境，请先运行 install.bat
    pause
    exit /b
)

:: 激活环境
call .venv\Scripts\activate.bat

:: 设置项目路径
set PYTHONPATH=src

echo [Selrena] System starting...
echo ---------------------------------------

:: 启动主程序
python -m cradle.main

:: 如果程序异常退出导致暂停，方便查看报错
if %errorlevel% neq 0 (
    echo.
    echo [Selrena] Process exited with error code %errorlevel%.
    pause
)
