@echo off
title WhisperDesk Studio Pro
cd /d "%~dp0"

:: 1. Priorizar el entorno virtual .venv si existe
if exist "%~dp0.venv\Scripts\python.exe" (
    if exist "%~dp0.venv\Scripts\pythonw.exe" (
        start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0WhisperDesk.pyw"
    ) else (
        start "" "%~dp0.venv\Scripts\python.exe" "%~dp0WhisperDesk.pyw"
    )
    exit /b 0
)

:: 2. Verificar dependencias en Python global
python -c "import flask, faster_whisper" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] Dependencias no encontradas. Ejecutando asistente de instalacion...
    call "%~dp0install.bat"
    exit /b 0
)

:: 3. Ejecutar con Python global
if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" "%~dp0WhisperDesk.pyw"
) else (
    start "" python "%~dp0WhisperDesk.pyw"
)
exit /b 0
