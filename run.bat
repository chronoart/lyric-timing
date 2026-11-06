@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
set "HF_HOME=%~dp0models"
set HF_HUB_OFFLINE=1
set GRADIO_ANALYTICS_ENABLED=False
set PYTHONIOENCODING=utf-8
echo Starting Lyric Timing... the browser will open automatically. Close this window to quit.
"%~dp0venv\Scripts\python.exe" app.py
pause
