@echo off
title WhisperDesk Studio Pro
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%~dp0WhisperDesk.pyw"
) else (
    python "%~dp0WhisperDesk.pyw"
)
