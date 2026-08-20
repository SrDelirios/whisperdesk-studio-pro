@echo off
title WhisperDesk
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    start "" "%~dp0.venv\Scripts\python.exe" "%~dp0run_app.py"
    exit /b 0
)

python -c "import flask, faster_whisper" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    call "%~dp0install.bat"
    exit /b 0
)

python "%~dp0run_app.py"
