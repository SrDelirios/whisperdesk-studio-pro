"""
WhisperDesk Studio Pro — Native Desktop Launcher
Abre la aplicación de escritorio en una ventana acelerada por hardware usando PyWebView y Edge WebView2.
"""
import sys
import os
import threading
import time
import socket
import logging
import ctypes
import subprocess

# Establecer ID de aplicación explícito en Windows para desacoplar el icono de la barra de tareas de python.exe
try:
    myappid = 'whisperdesk.studio.pro.v2'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

PORT = 54123
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")

def kill_orphan_port(port):
    """En Windows, libera el puerto si un proceso huérfano quedó abierto."""
    if os.name == 'nt':
        try:
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ if ($_ -ne {os.getpid()}) {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }} }}"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

def is_port_open(port, host='127.0.0.1'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0

def start_server():
    """Inicia el servidor Flask en segundo plano con soporte multihilo."""
    from app import app
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False, threaded=True)

def apply_window_icon():
    """Aplica el icono nativo .ico al HWND de la ventana para la barra de tareas y el título."""
    if not os.path.exists(ICON_PATH):
        return

    WM_SETICON = 0x80
    ICON_SMALL = 0
    ICON_BIG = 1
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010

    # Cargar recursos de icono nativo de 16x16 y 32x32
    hicon_small = ctypes.windll.user32.LoadImageW(0, ICON_PATH, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    hicon_big = ctypes.windll.user32.LoadImageW(0, ICON_PATH, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

    # Esperar a que la ventana de WebView2 esté creada y aplicar los iconos
    for _ in range(60):
        time.sleep(0.1)
        hwnd = ctypes.windll.user32.FindWindowW(None, "WhisperDesk Studio Pro")
        if hwnd:
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            if hicon_big:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            break

class DesktopBridge:
    """Puente JS para ejecutar operaciones nativas del sistema de archivos instantáneamente."""
    def __init__(self):
        self.window = None

    def select_file(self):
        """Abre el explorador nativo de Windows y devuelve la ruta sin transferir gigabytes por red."""
        try:
            import webview
            if self.window:
                file_types = (
                    'Archivos Multimedia (*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm;*.mp3;*.wav;*.flac;*.m4a;*.ogg)',
                    'Todos los archivos (*.*)'
                )
                result = self.window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=file_types
                )
                if result and len(result) > 0:
                    return result[0]
        except Exception as e:
            logging.error(f"Error en select_file: {e}")
        return None

    def select_folder(self):
        """Abre el diálogo nativo de Windows para seleccionar una carpeta."""
        try:
            import webview
            if self.window:
                result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
                if result and len(result) > 0:
                    return result[0]
        except Exception as e:
            logging.error(f"Error en select_folder: {e}")
        return None

def main():
    try:
        import webview
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], check=True)
        import webview

    # Asegurar que el puerto está limpio y lanzar siempre la última versión del backend
    kill_orphan_port(PORT)
    time.sleep(0.2)

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Esperar activamente a que el puerto responda
    for _ in range(40):
        if is_port_open(PORT):
            break
        time.sleep(0.1)

    # Instanciar el puente nativo
    bridge = DesktopBridge()

    # Hilo en segundo plano para inyectar el icono al HWND de Windows
    icon_thread = threading.Thread(target=apply_window_icon, daemon=True)
    icon_thread.start()

    # Crear ventana nativa de escritorio
    window = webview.create_window(
        title='WhisperDesk Studio Pro',
        url=f'http://127.0.0.1:{PORT}',
        width=1340,
        height=860,
        min_size=(960, 640),
        background_color='#07090E',
        text_select=True,
        confirm_close=False,
        js_api=bridge
    )
    bridge.window = window

    # Iniciar la ventana nativa (Edge Chromium WebView2) con el icono oficial
    webview.start(icon=ICON_PATH, debug=False)

if __name__ == '__main__':
    main()
