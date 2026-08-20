@echo off
title WhisperDesk Classic (Tkinter)
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%~dp0gui.py"
) else (
    python "%~dp0gui.py"
)
