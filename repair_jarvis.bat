@echo off
echo ==================================================
echo      JARVIS AUTO-REPAIR UTILITY
echo ==================================================
echo.
echo It looks like your LLM (llama-cpp-python) is trying to use NVIDIA CUDA
echo but cannot find the required DLLs.
echo.
echo If you DO NOT have an NVIDIA GPU or do not want to set up CUDA,
echo we should install the CPU-only version.
echo.
echo If you DO have an NVIDIA GPU, you need to install the CUDA Toolkit v12.
echo.
echo Choose an option:
echo 1. Force Re-install CPU-only version (Recommended for stability)
echo 2. Exit (I will fix CUDA myself)
echo.
set /p choice="Enter 1 or 2: "

if "%choice%"=="1" (
    echo.
    echo Uninstalling current package...
    pip uninstall -y llama-cpp-python
    echo.
    echo Installing CPU-only version...
    REM Force binary reinstall to avoid compiling from source if possible
    pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir
    echo.
    echo Done! Please restart JARVIS.
    pause
    exit
)

if "%choice%"=="2" (
    echo.
    echo Okay. Please install CUDA Toolkit 12.x or check your PATH environment variables.
    pause
    exit
)
