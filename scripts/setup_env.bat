@echo off
:: 获取脚本所在目录的上级目录作为项目根目录
set "PROJECT_ROOT=%~dp0.."
set "PIP_CACHE_DIR=%PROJECT_ROOT%\data\cache\pip"

:: 确保目录存在
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"

:: 设置环境变量
echo [Environment] Setting PIP_CACHE_DIR to: %PIP_CACHE_DIR%
echo [Environment] All pip downloads will now be cached in the project folder.

:: 启动一个新的 CMD 会话保留环境变量
cmd /k
