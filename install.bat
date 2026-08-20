@echo off
setlocal enabledelayedexpansion
title WhisperDesk Studio Pro - Instalador Automatico 1-Clic
chcp 65001 >nul

echo ===============================================================================
echo                WHISPERDESK STUDIO PRO - INSTALADOR 1-CLIC
echo ===============================================================================
echo.

cd /d "%~dp0"

:: 1. Verificar si Python esta instalado
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se encontro Python en el sistema.
    echo.
    echo Por favor instala Python 3.10 o superior marcando la casilla "Add Python to PATH":
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version') do set PY_VER=%%v
echo [OK] Python detectado: %PY_VER%
echo.

:: 2. Crear Entorno Virtual (.venv) si no existe
if not exist ".venv" (
    echo [*] Creando entorno virtual aislado (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Fallo al crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado con exito.
) else (
    echo [OK] Entorno virtual existente detectado.
)
echo.

:: 3. Activar Entorno Virtual
call .venv\Scripts\activate.bat

:: 4. Actualizar pip
echo [*] Actualizando gestor de paquetes pip...
python -m pip install --upgrade pip --quiet

:: 5. Detectar GPU NVIDIA y configurar PyTorch con aceleracion CUDA
echo [*] Detectando hardware grafico...
nvidia-smi >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] GPU NVIDIA detectada con soporte CUDA.
    echo [*] Instalando PyTorch con aceleracion CUDA 12.1...
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
) else (
    echo [INFO] No se detecto GPU NVIDIA dedicada. Usando modo CPU optimizado.
    echo [*] Instalando PyTorch para CPU...
    pip install torch torchaudio --quiet
)
echo.

:: 6. Instalar dependencias de requirements.txt
echo [*] Instalando dependencias de WhisperDesk Studio Pro...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ocurrio un problema al instalar las librerias.
    pause
    exit /b 1
)
echo [OK] Todas las dependencias de Python han sido instaladas.
echo.

:: 7. Verificar FFmpeg (Necesario para audio y video)
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] FFmpeg no esta en el PATH del sistema.
    echo [*] Verificando binario local...
    if not exist "ffmpeg.exe" (
        echo [*] Descargando binario portatil de FFmpeg...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'ffmpeg.zip'; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force; Copy-Item 'ffmpeg_temp\*\bin\*.exe' -Destination '.' -Force; Remove-Item -Recurse -Force 'ffmpeg_temp', 'ffmpeg.zip'"
    )
) else (
    echo [OK] FFmpeg detectado correctamente en el sistema.
)
echo.

:: 8. Crear acceso directo en el Escritorio
if exist "create_shortcut.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "create_shortcut.ps1" >nul 2>&1
    echo [OK] Acceso directo creado en tu Escritorio.
)
echo.

echo ===============================================================================
echo          INSTALACION COMPLETADA CON EXITO - INICIANDO WHISPERDESK
echo ===============================================================================
echo.

:: 9. Iniciar la aplicacion
start "" "%~dp0WhisperDesk_Studio.bat"
exit /b 0
