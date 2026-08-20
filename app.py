import os
import re
import json
import time
import threading
import queue
import subprocess
import shutil
import urllib.parse
from flask import Flask, request, jsonify, Response, send_from_directory, render_template
from werkzeug.utils import secure_filename
from transcriber import VideoConverter, WhisperTranscriber
from summarizer import MeetingActaSummarizer
from diarizer import SpeakerDiarizer
from youtube import YouTubeAudioExtractor
from database import DatabaseManager

app = Flask(__name__)

# Configuración básica
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 * 1024  # 500 GB max upload
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DEFAULT_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

db = DatabaseManager()

def load_app_config():
    """Carga la configuración persistente del usuario."""
    cfg = {
        "output_folder": DEFAULT_OUTPUT_FOLDER,
        "default_model": "large-v3-turbo"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception:
            pass
    return cfg

def save_app_config(cfg):
    """Guarda la configuración persistente en disco."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_output_folder():
    """Obtiene la carpeta de salida configurada actualmente."""
    cfg = load_app_config()
    out = cfg.get('output_folder', DEFAULT_OUTPUT_FOLDER)
    os.makedirs(out, exist_ok=True)
    return out

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DEFAULT_OUTPUT_FOLDER, exist_ok=True)

# Auto migrar archivos legacy a SQLite en segundo plano sin bloquear el arranque
try:
    threading.Thread(target=lambda: db.auto_import_txt_files(DEFAULT_OUTPUT_FOLDER, UPLOAD_FOLDER), daemon=True).start()
except Exception:
    pass

# Instancia global para evitar recargar el modelo continuamente
transcriber = WhisperTranscriber()
current_cancel_event = threading.Event()

def make_safe_filename(name):
    """Sanitiza nombres de archivo preservando caracteres unicode válidos."""
    if not name:
        return ""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', str(name))
    return cleaned.strip('. ')

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "El archivo excede el tamaño permitido"}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Error interno del servidor al procesar el archivo"}), 500

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/')
def index():
    """Servir la interfaz web de escritorio."""
    return render_template('index.html')

@app.route('/api/hardware', methods=['GET'])
def get_hardware_status():
    """Retorna información en tiempo real sobre la GPU (CUDA) y Ollama."""
    cuda_available = False
    device_name = "CPU"
    vram_info = "N/A"
    
    try:
        import torch
        if torch.cuda.is_available():
            cuda_available = True
            device_name = torch.cuda.get_device_name(0)
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            vram_info = f"{allocated:.1f}GB / {total:.1f}GB"
    except Exception:
        pass

    models = MeetingActaSummarizer.get_ollama_models()
    ollama_connected = any("Ollama:" in m for m in models)

    return jsonify({
        "cuda": cuda_available,
        "gpu": device_name,
        "vram": vram_info,
        "ollama_connected": ollama_connected,
        "ollama_models": models
    })

@app.route('/api/ollama/start', methods=['POST'])
@app.route('/api/start-ollama', methods=['POST'])
def start_ollama():
    """Inicia el servicio Ollama en Windows si está apagado."""
    ollama_bin = shutil.which("ollama") or os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if ollama_bin and os.path.exists(ollama_bin):
        try:
            subprocess.Popen([ollama_bin, "serve"], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for _ in range(4):
                time.sleep(1.0)
                models = MeetingActaSummarizer.get_ollama_models()
                if any("Ollama:" in m for m in models):
                    return jsonify({"status": "started", "models": models})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    models = MeetingActaSummarizer.get_ollama_models()
    return jsonify({"status": "checked", "models": models})

@app.route('/api/models', methods=['GET'])
def get_models():
    """Obtiene la lista de modelos Whisper disponibles."""
    models = WhisperTranscriber.get_available_models()
    return jsonify(models)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Sube un archivo de video o audio y devuelve sus metadatos."""
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo en la solicitud"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
    original_name = file.filename
    filename = make_safe_filename(file.filename)
    if not filename:
        filename = f"file_{int(time.time())}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    size = os.path.getsize(file_path)
    ext = os.path.splitext(filename)[1].lower()
    info = VideoConverter.get_media_info(file_path)
    
    return jsonify({
        "name": filename,
        "original_name": original_name,
        "size": size,
        "duration": info.get('duration', 0.0),
        "type": ext,
        "path": file_path,
        "media_url": f"/api/media/{filename}"
    })

@app.route('/api/load_direct', methods=['POST'])
def load_direct_file():
    """Carga un archivo local directamente por su ruta sin transferir gigabytes por red (0 segundos)."""
    data = request.json
    if not data or 'file_path' not in data:
        return jsonify({"error": "Falta 'file_path'"}), 400
        
    raw_path = os.path.abspath(data['file_path'])
    if not os.path.exists(raw_path):
        return jsonify({"error": f"El archivo no existe en: {raw_path}"}), 404
        
    original_name = os.path.basename(raw_path)
    size = os.path.getsize(raw_path)
    ext = os.path.splitext(original_name)[1].lower()
    safe_base = make_safe_filename(os.path.splitext(original_name)[0])
    
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    is_video = ext in video_exts
    
    if is_video:
        # Extraer únicamente el audio WAV 16kHz en uploads/ directamente desde el archivo original
        out_wav = os.path.join(UPLOAD_FOLDER, f"{safe_base}_{int(time.time())}.wav")
        try:
            audio_path = VideoConverter.convert(raw_path, out_wav)
            out_name = os.path.basename(audio_path)
            info = VideoConverter.get_media_info(audio_path)
            return jsonify({
                "name": original_name,
                "original_name": original_name,
                "size": size,
                "duration": info.get('duration', 0.0),
                "type": ext,
                "is_video": True,
                "path": audio_path,
                "media_url": f"/api/media/{out_name}",
                "direct_load": True
            })
        except Exception as e:
            return jsonify({"error": f"Error extrayendo audio con FFmpeg: {str(e)}"}), 500
    else:
        # Es directamente un archivo de audio (.mp3, .wav, .m4a, .flac, etc.)
        info = VideoConverter.get_media_info(raw_path)
        import urllib.parse
        encoded_path = urllib.parse.quote(raw_path)
        return jsonify({
            "name": original_name,
            "original_name": original_name,
            "size": size,
            "duration": info.get('duration', 0.0),
            "type": ext,
            "is_video": False,
            "path": raw_path,
            "media_url": f"/api/media_direct?path={encoded_path}",
            "direct_load": True
        })

@app.route('/api/media_direct', methods=['GET'])
def stream_direct_media():
    """Sirve archivos de audio directamente desde cualquier ruta del sistema de archivos local."""
    import urllib.parse
    raw_param = request.args.get('path', '')
    if not raw_param:
        return jsonify({"error": "Falta parámetro 'path'"}), 400
    
    file_path = urllib.parse.unquote(raw_param)
    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado"}), 404
        
    folder = os.path.dirname(os.path.abspath(file_path))
    filename = os.path.basename(file_path)
    return send_from_directory(folder, filename)

@app.route('/api/convert', methods=['POST'])
def convert_video():
    """Convierte un archivo de video a audio WAV."""
    data = request.json
    if not data or 'file_path' not in data:
        return jsonify({"error": "Falta 'file_path' en la solicitud"}), 400
        
    input_path = data['file_path']
    if not os.path.exists(input_path):
        return jsonify({"error": "El archivo especificado no existe"}), 404
        
    try:
        output_path = VideoConverter.convert(input_path)
        out_name = os.path.basename(output_path)
        return jsonify({"audio_path": output_path, "media_url": f"/api/media/{out_name}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/youtube', methods=['POST'])
def process_youtube():
    """Descarga el audio de una URL de YouTube y devuelve la ruta del archivo."""
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"error": "Falta la URL de YouTube"}), 400

    url = data['url']
    if not YouTubeAudioExtractor.is_youtube_url(url):
        return jsonify({"error": "URL de YouTube no válida"}), 400

    try:
        info = YouTubeAudioExtractor.download_audio(url, UPLOAD_FOLDER)
        out_name = os.path.basename(info['audio_path'])
        return jsonify({
            "name": info['title'],
            "audio_path": info['audio_path'],
            "duration": info['duration'],
            "url": info['url'],
            "media_url": f"/api/media/{out_name}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/media/<path:filename>', methods=['GET'])
@app.route('/media/<path:filename>', methods=['GET'])
def stream_media(filename):
    """Sirve archivos multimedia desde uploads o carpetas de salida para el reproductor de audio."""
    clean_name = os.path.basename(filename)
    out_dir = get_output_folder()
    for folder in [UPLOAD_FOLDER, out_dir, DEFAULT_OUTPUT_FOLDER]:
        target = os.path.join(folder, clean_name)
        if os.path.exists(target):
            return send_from_directory(folder, clean_name)
    return jsonify({"error": "Archivo multimedia no encontrado"}), 404

@app.route('/api/cancel', methods=['POST'])
def cancel_transcription():
    """Aborta el proceso de transcripción en curso."""
    current_cancel_event.set()
    return jsonify({"status": "cancelling"})

@app.route('/api/transcribe', methods=['GET'])
def transcribe():
    """Endpoint Server-Sent Events (SSE) para transcribir y emitir progreso en tiempo real."""
    file_path = request.args.get('file_path')
    model_name = request.args.get('model', 'large-v3-turbo')
    language = request.args.get('language', None)
    if language == 'auto':
        language = None
    output_format = request.args.get('output_format', 'txt')
    custom_name = request.args.get('custom_name', '')
    project = request.args.get('project', '')

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    current_cancel_event.clear()

    def generate_events():
        q = queue.Queue()
        start_time = time.time()
        
        def worker():
            try:
                transcriber.load_model(model_name)
                
                def progress_cb(current, total, *args):
                    if current_cancel_event.is_set():
                        return
                    text = args[-1] if args else ""
                    q.put({"type": "progress", "current": current, "total": total, "text": text})
                
                result = transcriber.transcribe(
                    file_path, 
                    language=language, 
                    progress_callback=progress_cb,
                    cancel_event=current_cancel_event
                )
                
                if result.get('cancelled'):
                    q.put({"type": "cancelled"})
                else:
                    q.put({"type": "complete", "result": result})
            except Exception as e:
                q.put({"type": "error", "message": str(e)})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        
        try:
            while True:
                msg = q.get()
                if msg["type"] == "progress":
                    progress_pct = (msg["current"] / msg["total"] * 100) if msg["total"] > 0 else 0
                    data = {
                        "progress": min(progress_pct, 100),
                        "current": msg["current"],
                        "total": msg["total"],
                        "text": msg["text"]
                    }
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"

                elif msg["type"] == "cancelled":
                    yield f"event: cancelled\ndata: {json.dumps({'message': 'Cancelado por el usuario'})}\n\n"
                    break
                    
                elif msg["type"] == "complete":
                    result = msg["result"]
                    processing_duration = time.time() - start_time
                    
                    if output_format == 'srt':
                        final_content = WhisperTranscriber.format_as_srt(result)
                        ext = 'srt'
                    elif output_format == 'vtt':
                        final_content = WhisperTranscriber.format_as_vtt(result)
                        ext = 'vtt'
                    else:
                        final_content = result.get('speaker_text', result.get('text', ''))
                        ext = 'txt'
                        
                    if custom_name:
                        safe_name = make_safe_filename(custom_name)
                    else:
                        safe_name = os.path.splitext(os.path.basename(file_path))[0]
                        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
                        while any(safe_name.lower().endswith(vext) for vext in video_exts):
                            safe_name = os.path.splitext(safe_name)[0]
                        safe_name = f"{safe_name}_{int(time.time())}"

                    output_filename = f"{safe_name}.{ext}"

                    output_root = get_output_folder()
                    if project and project != "General":
                        dest_folder = os.path.join(output_root, make_safe_filename(project))
                    else:
                        dest_folder = output_root
                    os.makedirs(dest_folder, exist_ok=True)

                    output_filepath = os.path.join(dest_folder, output_filename)
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write(final_content)
                        
                    update_session_index(output_filename, file_path, project)
                    
                    if file_path.startswith(UPLOAD_FOLDER):
                        media_url = f"/api/media/{urllib.parse.quote(os.path.basename(file_path))}"
                    else:
                        media_url = f"/api/media_direct?path={urllib.parse.quote(file_path)}"
                        
                    session_id = f"session_{safe_name}"
                    try:
                        db.save_session({
                            "session_id": session_id,
                            "title": safe_name,
                            "project": project or "General",
                            "created_at": time.time(),
                            "audio_path": file_path,
                            "audio_filename": os.path.basename(file_path),
                            "media_url": media_url,
                            "duration": result.get('duration', processing_duration),
                            "plain_text": result.get('plain_text', result.get('text', '')),
                            "speaker_text": result.get('speaker_text', ''),
                            "segments": result.get('segments', []),
                            "file_format": ext
                        })
                    except Exception as e:
                        pass
                        
                    data = {
                        "session_id": session_id,
                        "text": result.get('text', ''),
                        "plain_text": result.get('plain_text', result.get('text', '')),
                        "speaker_text": result.get('speaker_text', ''),
                        "segments": result.get('segments', []),
                        "file": output_filename,
                        "duration": processing_duration,
                        "language": result.get('language', 'es'),
                        "custom_name": safe_name,
                        "media_url": media_url
                    }
                    yield f"event: complete\ndata: {json.dumps(data)}\n\n"
                    break
                    
                elif msg["type"] == "error":
                    yield f"event: error\ndata: {json.dumps({'message': msg['message']})}\n\n"
                    break
        except GeneratorExit:
            pass

    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/api/summarize', methods=['POST'])
def generate_summary():
    """Genera el Acta Oficial de Sesión usando Ollama o el motor heurístico."""
    data = request.json or {}
    if not data or 'text' not in data:
        return jsonify({"error": "Falta el texto de la transcripción"}), 400

    transcript = data['text']
    title = data.get('title', 'Reunión de Trabajo')
    duration = data.get('duration', 'N/A')
    model = data.get('model', 'qwen2.5:latest')
    session_id = data.get('session_id')

    try:
        if "Offline" in model or "Heurístico" in model or "Desconectado" in model:
            summary = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration)
        else:
            summary = MeetingActaSummarizer.generate_summary_ollama(transcript, title=title, duration=duration, model=model)
        
        if session_id:
            try:
                db.update_summary(session_id, summary)
            except Exception:
                pass
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/summarize_stream', methods=['POST'])
def generate_summary_stream():
    """Genera el Acta Oficial transmitiendo tokens por Server-Sent Events en tiempo real."""
    data = request.json or {}
    transcript = data.get('text', '')
    title = data.get('title', 'Reunión de Trabajo')
    duration = data.get('duration', 'N/A')
    model = data.get('model', 'llama3.2:latest')
    session_id = data.get('session_id')

    if not transcript:
        return jsonify({"error": "Falta el texto de transcripción"}), 400

    def event_stream():
        accumulated_summary = []
        try:
            if "Offline" in model or "Heurístico" in model or "Desconectado" in model:
                acta = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration)
                accumulated_summary.append(acta)
                yield f"data: {json.dumps({'token': acta, 'done': True})}\n\n"
            else:
                for chunk in MeetingActaSummarizer.stream_summary_ollama(transcript, title=title, duration=duration, model=model):
                    if chunk.get('token'):
                        accumulated_summary.append(chunk['token'])
                    yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            fallback = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration)
            accumulated_summary.append(fallback)
            yield f"data: {json.dumps({'token': fallback, 'done': True})}\n\n"
        finally:
            if session_id and accumulated_summary:
                try:
                    full_text = "".join(accumulated_summary)
                    db.update_summary(session_id, full_text)
                except Exception:
                    pass

    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """Obtiene el historial estructurado completo desde la base de datos SQLite instantáneamente."""
    project = request.args.get('project', '')
    search = request.args.get('search', '')
    sessions = db.list_sessions(project=project, search=search)
    return jsonify(sessions)

@app.route('/api/session/<session_id>', methods=['GET'])
def get_session_detail(session_id):
    """Obtiene el detalle completo estructurado de una sesión (hablantes, texto limpio, audio y acta)."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Sesión no encontrada"}), 404
    return jsonify(session)

@app.route('/api/session/<session_id>/summary', methods=['POST'])
def save_session_summary(session_id):
    """Guarda el acta en la base de datos para la sesión."""
    data = request.json or {}
    summary = data.get('summary', '')
    db.update_summary(session_id, summary)
    return jsonify({"success": True})

@app.route('/api/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Elimina una sesión de la base de datos y su archivo correspondiente."""
    session = db.get_session(session_id)
    if session:
        # Intentar eliminar archivo físico en output
        try:
            out_dir = get_output_folder()
            proj = session.get('project', '')
            base_dir = os.path.join(out_dir, proj) if (proj and proj != 'General') else out_dir
            for ext in ['.txt', '.srt', '.vtt']:
                f_path = os.path.join(base_dir, f"{session['title']}{ext}")
                if os.path.exists(f_path):
                    os.remove(f_path)
        except Exception:
            pass
        db.delete_session(session_id)
        return jsonify({"success": True})
    return jsonify({"error": "Sesión no encontrada"}), 404

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Obtiene la configuración actual de rutas y preferencias."""
    cfg = load_app_config()
    return jsonify({
        "output_folder": get_output_folder(),
        "default_output_folder": DEFAULT_OUTPUT_FOLDER,
        "default_model": cfg.get("default_model", "large-v3-turbo")
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Actualiza la ruta de guardado o configuraciones de la aplicación."""
    data = request.json or {}
    cfg = load_app_config()

    if data.get('reset_output'):
        cfg['output_folder'] = DEFAULT_OUTPUT_FOLDER
    elif data.get('output_folder'):
        new_folder = os.path.abspath(data['output_folder'].strip())
        os.makedirs(new_folder, exist_ok=True)
        cfg['output_folder'] = new_folder

    if data.get('default_model'):
        cfg['default_model'] = data['default_model']

    save_app_config(cfg)
    return jsonify({
        "success": True,
        "output_folder": get_output_folder(),
        "default_output_folder": DEFAULT_OUTPUT_FOLDER
    })

@app.route('/api/select-folder', methods=['POST'])
def select_folder_native():
    """Abre el selector de carpetas nativo de Windows (Tkinter/Desktop)."""
    selected_path = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected_path = filedialog.askdirectory(title="Seleccionar Carpeta de Guardado para Transcripciones", initialdir=get_output_folder())
        root.destroy()
    except Exception as e:
        pass

    if selected_path:
        cfg = load_app_config()
        cfg['output_folder'] = os.path.abspath(selected_path)
        save_app_config(cfg)
        return jsonify({"success": True, "path": cfg['output_folder']})
    return jsonify({"success": False, "cancelled": True})

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """Lista todos los proyectos disponibles en la carpeta de salida activa."""
    projects = []
    out_dir = get_output_folder()
    try:
        general_count = sum(1 for f in os.listdir(out_dir)
                           if os.path.isfile(os.path.join(out_dir, f)) and f != '.gitkeep' and f != '.sessions_index.json')
        projects.append({"name": "General", "path": "", "file_count": general_count})

        for entry in sorted(os.listdir(out_dir)):
            full_path = os.path.join(out_dir, entry)
            if os.path.isdir(full_path) and not entry.startswith('.'):
                count = sum(1 for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f)))
                projects.append({"name": entry, "path": entry, "file_count": count})

        return jsonify(projects)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Crea un nuevo proyecto en la carpeta de salida activa."""
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"error": "Nombre del proyecto requerido"}), 400

    project_name = make_safe_filename(data['name'])
    if not project_name:
        return jsonify({"error": "Nombre de proyecto no válido"}), 400

    out_dir = get_output_folder()
    project_path = os.path.join(out_dir, project_name)
    if os.path.exists(project_path):
        return jsonify({"error": "El proyecto ya existe"}), 409

    try:
        os.makedirs(project_path, exist_ok=True)
        return jsonify({"name": project_name, "path": project_name, "file_count": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_name>', methods=['DELETE'])
def delete_project(project_name):
    """Elimina un proyecto."""
    out_dir = get_output_folder()
    project_path = os.path.join(out_dir, make_safe_filename(project_name))
    if not os.path.exists(project_path) or not os.path.isdir(project_path):
        return jsonify({"error": "Proyecto no encontrado"}), 404
    try:
        shutil.rmtree(project_path)
        return jsonify({"message": "Proyecto eliminado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Obtiene el historial de transcripciones de la carpeta de salida activa."""
    project = request.args.get('project', '')
    out_dir = get_output_folder()
    base_dir = os.path.join(out_dir, project) if (project and project != 'General') else out_dir

    files = []
    try:
        if not os.path.exists(base_dir):
            return jsonify(files)

        for filename in os.listdir(base_dir):
            if filename == '.gitkeep' or filename == '.sessions_index.json':
                continue
            file_path = os.path.join(base_dir, filename)
            if os.path.isfile(file_path):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(file_path),
                    "created": os.path.getmtime(file_path),
                    "project": project or "General"
                })
        files.sort(key=lambda x: x["created"], reverse=True)
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Descarga un archivo transcrito."""
    project = request.args.get('project', '')
    out_dir = get_output_folder()
    base_dir = os.path.join(out_dir, project) if (project and project != 'General') else out_dir
    try:
        return send_from_directory(base_dir, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "Archivo no encontrado"}), 404

def update_session_index(output_filename, original_media_path, project=""):
    """Guarda en un índice persistente la ruta del audio asociado a cada transcripción."""
    try:
        out_dir = get_output_folder()
        index_file = os.path.join(out_dir, ".sessions_index.json")
        index_data = {}
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            except Exception:
                index_data = {}
        index_data[output_filename] = {
            "media_path": original_media_path,
            "project": project,
            "updated_at": time.time()
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

@app.route('/api/copy', methods=['POST'])
def copy_text():
    """Lee el contenido de un archivo de salida y localiza el audio asociado si existe."""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({"error": "Nombre de archivo faltante"}), 400

    project = data.get('project', '')
    out_dir = get_output_folder()
    base_dir = os.path.join(out_dir, project) if (project and project != 'General') else out_dir
    filename = data['filename']
    file_path = os.path.join(base_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        media_url = None
        audio_name = None
        has_audio = False

        # 1. Buscar en el índice de sesiones persistente
        index_file = os.path.join(out_dir, ".sessions_index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                if filename in index_data:
                    m_path = index_data[filename].get('media_path')
                    if m_path and os.path.exists(m_path):
                        audio_name = os.path.basename(m_path)
                        has_audio = True
                        if m_path.startswith(UPLOAD_FOLDER):
                            media_url = f"/api/media/{urllib.parse.quote(audio_name)}"
                        else:
                            media_url = f"/api/media_direct?path={urllib.parse.quote(m_path)}"
            except Exception:
                pass

        # 2. Si no se encontró en el índice, buscar coincidencias directas en UPLOAD_FOLDER
        if not media_url:
            base_name = os.path.splitext(filename)[0]
            clean_base = re.sub(r'_\d{10}$', '', base_name)
            media_exts = ('.wav', '.mp3', '.m4a', '.mp4', '.mkv', '.flac', '.webm', '.ogg')

            for upload_file in sorted(os.listdir(UPLOAD_FOLDER)):
                u_base, u_ext = os.path.splitext(upload_file)
                if u_ext.lower() in media_exts:
                    if u_base == base_name or u_base == clean_base or base_name.startswith(u_base) or clean_base.startswith(u_base):
                        media_url = f"/api/media/{urllib.parse.quote(upload_file)}"
                        audio_name = upload_file
                        has_audio = True
                        break

        return jsonify({
            "content": content,
            "has_audio": has_audio,
            "media_url": media_url,
            "audio_name": audio_name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-file', methods=['POST'])
def delete_file_endpoint():
    """Elimina un archivo de transcripción."""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({"error": "Nombre de archivo faltante"}), 400

    project = data.get('project', '')
    out_dir = get_output_folder()
    base_dir = os.path.join(out_dir, project) if (project and project != 'General') else out_dir
    file_path = os.path.join(base_dir, data['filename'])

    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    try:
        os.remove(file_path)
        return jsonify({"message": "Archivo eliminado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """Abre la carpeta en el Explorador de Windows."""
    data = request.json or {}
    target = data.get('target', 'output')
    folder = UPLOAD_FOLDER if target == 'uploads' else get_output_folder()
    try:
        if os.name == 'nt':
            os.startfile(folder)
        return jsonify({"success": True, "path": folder})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clean-temp', methods=['POST'])
def clean_temp():
    """Limpia archivos temporales de audio en uploads/."""
    deleted_count = 0
    try:
        for f in os.listdir(UPLOAD_FOLDER):
            if f != '.gitkeep':
                p = os.path.join(UPLOAD_FOLDER, f)
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                        deleted_count += 1
                except Exception:
                    pass
        return jsonify({"success": True, "deleted": deleted_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=54123, debug=False, threaded=True)
