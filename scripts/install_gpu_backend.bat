@echo off
setlocal

REM Activate environment variables for CUDA compilation
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

REM Add the virtual environment Scripts folder to PATH so ninja.exe can be found
set "PATH=D:\elise\Cradle_Selrena\.venv\Scripts;%PATH%"

REM Set CMake arguments for GPU build
set CMAKE_ARGS=-DGGML_CUDA=on -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_FLAGS="-allow-unsupported-compiler"
set CMAKE_GENERATOR=Ninja

echo Starting compilation of llama-cpp-python with CUDA support...
echo This process may take several minutes.

REM detailed verbose install
python -m pip install "llama-cpp-python>=0.3.16" --upgrade --force-reinstall --no-cache-dir --verbose

if %ERRORLEVEL% EQU 0 (
    echo Installation successful!
) else (
    echo Installation failed.
)
endlocal
