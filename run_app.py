import os
import sys
import time
import subprocess
import threading

# Asegurar que el directorio del proyecto está en el PATH de Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

def start_server():
    """Inicia el servidor Flask en segundo plano con soporte multihilo."""
    from app import app
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='127.0.0.1', port=54123, debug=False, use_reloader=False, threaded=True)

def main():
    # Iniciar servidor en hilo daemon
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    # Ruta de Microsoft Edge
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]

    edge_exe = None
    for path in edge_paths:
        if os.path.exists(path):
            edge_exe = path
            break

    url = "http://127.0.0.1:54123"

    if edge_exe:
        # Abrir Edge en modo Aplicación nativa de escritorio (sin barra de navegador)
        subprocess.run([edge_exe, f"--app={url}", "--title=WhisperDesk"])
    else:
        import webbrowser
        webbrowser.open(url)

if __name__ == '__main__':
    main()
