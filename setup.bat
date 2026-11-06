@echo off
setlocal
cd /d "%~dp0"
rem Everything (uv, Python, packages, model) is installed inside this folder.
set "UV_INSTALL_DIR=%~dp0tools"
set "UV_NO_MODIFY_PATH=1"
set "UV_PYTHON_INSTALL_DIR=%~dp0tools\python"
set "UV_CACHE_DIR=%~dp0tools\cache"
set "HF_HOME=%~dp0models"
set "UV=%~dp0tools\uv.exe"

echo ============================================================
echo  Lyric Timing - setup (first time only, needs internet)
echo  Downloads about 6 GB. This can take 10-30 minutes.
echo ============================================================
echo.

if not exist "%UV%" (
  echo [1/5] Downloading uv ^(Python installer^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  if not exist "%UV%" goto :fail
) else (
  echo [1/5] uv found.
)

if not exist "venv\Scripts\python.exe" (
  echo [2/5] Installing Python 3.10 and creating venv...
  "%UV%" venv venv --python 3.10 || goto :fail
) else (
  echo [2/5] venv found.
)

where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
  echo [3/5] NVIDIA GPU detected: installing PyTorch with CUDA...
  set "TORCH_INDEX=https://download.pytorch.org/whl/cu128"
) else (
  echo [3/5] No NVIDIA GPU: installing CPU PyTorch ^(analysis will be slower^)...
  set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
)
"%UV%" pip install --python venv\Scripts\python.exe torch==2.11.0 torchaudio --index-url %TORCH_INDEX% || goto :fail

echo [4/5] Installing other packages...
"%UV%" pip install --python venv\Scripts\python.exe -r requirements.txt || goto :fail

echo [5/5] Downloading speech recognition model...
venv\Scripts\python.exe download_model.py || goto :fail

rem Remove the download cache (saves about 5 GB)
"%UV%" cache clean >nul 2>&1

echo.
echo ============================================================
echo  Setup finished. Double-click run.bat to start.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ************************************************************
echo  Setup failed. Check your internet connection and run
echo  setup.bat again (finished steps are skipped).
echo ************************************************************
pause
exit /b 1
