import os
import re
import json
import time
import threading
import queue
import subprocess
import shutil
import urllib.parse
import io
from flask import Flask, request, jsonify, Response, send_from_directory, render_template, send_file, stream_with_context
from werkzeug.utils import secure_filename
from transcriber import VideoConverter, WhisperTranscriber
from summarizer import MeetingActaSummarizer
from diarizer import SpeakerDiarizer
from youtube import YouTubeAudioExtractor
from database import DatabaseManager
from exporter import MeetingMinutesExporter

app = Flask(__name__)

# Configuración básica
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 * 1024  # 500 GB max upload
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DEFAULT_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

db = DatabaseManager()

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DEFAULT_OUTPUT_FOLDER, exist_ok=True)

# Estado global de la tarea actual
current_task = {
    "status": "idle",       # idle, converting, transcribing, diarizing, completed, error
    "progress": 0,          # 0 a 100
    "step_detail": "Listo para iniciar",
    "device_info": "GPU NVIDIA RTX 4070 Activa",
    "result": None,
    "error": None,
    "start_time": None
}

task_lock = threading.Lock()

def load_app_config():
    """Carga la configuración persistente desde config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "output_folder": DEFAULT_OUTPUT_FOLDER,
        "default_model": "large-v3-turbo",
        "default_device": "cuda",
        "default_language": "auto",
        "save_txt": True,
        "save_srt": True,
        "save_vtt": True,
        "save_json": False,
        "auto_diarize": False,
        "gemini_api_key": ""
    }

def save_app_config(cfg):
    """Guarda la configuración persistente en config.json."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def format_timestamp(seconds: float) -> str:
    """Convierte segundos a formato HH:MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def async_transcription_worker(file_path, original_filename, model_name, language,
                               selected_formats, project_name="General", custom_name=""):
    """Hilo trabajador que ejecuta la conversión, transcripción y diarización completa."""
    global current_task
    cfg = load_app_config()
    output_dir = cfg.get("output_folder", DEFAULT_OUTPUT_FOLDER)
    gemini_key = cfg.get("gemini_api_key", "")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(original_filename)[0]
    display_title = custom_name.strip() if custom_name and custom_name.strip() else base_name

    try:
        # Paso 1: Conversión y Extracción de Audio
        with task_lock:
            current_task["status"] = "converting"
            current_task["progress"] = 10
            current_task["step_detail"] = "Extrayendo y normalizando pista de audio (16kHz WAV)..."

        audio_wav_path = VideoConverter.extract_audio(file_path)
        duration_sec = VideoConverter.get_audio_duration(audio_wav_path)
        duration_formatted = format_timestamp(duration_sec)

        # Paso 2: Transcripción con Faster-Whisper
        with task_lock:
            current_task["status"] = "transcribing"
            current_task["progress"] = 25
            current_task["step_detail"] = f"Transcribiendo con modelo {model_name} en GPU..."

        def on_transcribe_progress(percent, msg):
            with task_lock:
                # Mapear 0-100% de transcripción al rango 25%-75% del proceso total
                current_task["progress"] = 25 + int(percent * 0.50)
                current_task["step_detail"] = msg

        transcriber = WhisperTranscriber(model_size=model_name, device="cuda")
        raw_result = transcriber.transcribe(
            audio_wav_path,
            language=language if language != 'auto' else None,
            progress_callback=on_transcribe_progress
        )

        segments = raw_result.get("segments", [])
        detected_lang = raw_result.get("language", "es")

        # Paso 3: Diarización e Identificación de Hablantes
        with task_lock:
            current_task["status"] = "diarizing"
            current_task["progress"] = 80
            current_task["step_detail"] = "Segmentando e identificando hablantes por voz..."

        diarizer = SpeakerDiarizer()
        diarized_segments = diarizer.diarize(audio_wav_path, segments)

        # Construir textos
        speaker_lines = []
        plain_lines = []
        for s in diarized_segments:
            start_str = format_timestamp(s["start"])
            end_str = format_timestamp(s["end"])
            speaker_lines.append(f"⏱ {start_str} - {end_str} [{s['speaker']}]: {s['text']}")
            plain_lines.append(s["text"])

        full_speaker_text = "\n".join(speaker_lines)
        full_plain_text = "\n".join(plain_lines)

        # Paso 4: Exportar Archivos
        with task_lock:
            current_task["status"] = "saving"
            current_task["progress"] = 92
            current_task["step_detail"] = "Generando archivos TXT, SRT, VTT y estructurando datos..."

        saved_files = {}
        safe_name = re.sub(r'[^\w\-_\. ]', '_', display_title).strip()

        # Guardar TXT con Hablantes
        txt_path = os.path.join(output_dir, f"{safe_name}_transcripcion.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"PROYECTO: {project_name}\n")
            f.write(f"TITULO: {display_title}\n")
            f.write(f"FECHA: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"DURACION: {duration_formatted}\n")
            f.write(f"IDIOMA DETECTADO: {detected_lang}\n")
            f.write("=" * 60 + "\n\n")
            f.write(full_speaker_text)
        saved_files["txt"] = txt_path

        # Guardar SRT
        srt_path = os.path.join(output_dir, f"{safe_name}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, s in enumerate(diarized_segments, start=1):
                s_start = f"{int(s['start']//3600):02d}:{int((s['start']%3600)//60):02d}:{int(s['start']%60):02d},{int((s['start']%1)*1000):03d}"
                s_end = f"{int(s['end']//3600):02d}:{int((s['end']%3600)//60):02d}:{int(s['end']%60):02d},{int((s['end']%1)*1000):03d}"
                f.write(f"{i}\n{s_start} --> {s_end}\n[{s['speaker']}]: {s['text']}\n\n")
        saved_files["srt"] = srt_path

        # Guardar VTT
        vtt_path = os.path.join(output_dir, f"{safe_name}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for s in diarized_segments:
                v_start = f"{int(s['start']//3600):02d}:{int((s['start']%3600)//60):02d}:{int(s['start']%60):02d}.{int((s['start']%1)*1000):03d}"
                v_end = f"{int(s['end']//3600):02d}:{int((s['end']%3600)//60):02d}:{int(s['end']%60):02d}.{int((s['end']%1)*1000):03d}"
                f.write(f"{v_start} --> {v_end}\n[{s['speaker']}]: {s['text']}\n\n")
        saved_files["vtt"] = vtt_path

        # Guardar en Base de Datos SQLite
        session_id = f"sess_{int(time.time()*1000)}"
        db.save_session(
            session_id=session_id,
            title=display_title,
            project=project_name,
            duration_sec=duration_sec,
            duration_str=duration_formatted,
            language=detected_lang,
            model_used=model_name,
            speaker_text=full_speaker_text,
            plain_text=full_plain_text,
            segments=diarized_segments,
            files=saved_files
        )

        final_data = {
            "session_id": session_id,
            "title": display_title,
            "project": project_name,
            "duration": duration_formatted,
            "duration_sec": duration_sec,
            "language": detected_lang,
            "speaker_text": full_speaker_text,
            "plain_text": full_plain_text,
            "segments": diarized_segments,
            "files": saved_files,
            "summary": ""
        }

        with task_lock:
            current_task["status"] = "completed"
            current_task["progress"] = 100
            current_task["step_detail"] = "Transcripción y análisis completados con éxito."
            current_task["result"] = final_data

    except Exception as e:
        with task_lock:
            current_task["status"] = "error"
            current_task["error"] = str(e)
            current_task["step_detail"] = f"Error en el proceso: {str(e)}"
    finally:
        # Limpiar archivo temporal de subida si existe
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

# =========================================================================
# RUTAS DE LA API REST
# =========================================================================

@app.route('/')
def index():
    """Página principal de WhisperDesk Studio Pro."""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_task_status():
    """Obtiene el estado de la tarea en ejecución en tiempo real."""
    with task_lock:
        return jsonify(current_task)

@app.route('/api/hardware', methods=['GET'])
def get_hardware_info():
    """Obtiene información sobre la GPU NVIDIA, Ollama y Google Gemini."""
    gpu_info = WhisperTranscriber.get_gpu_info()
    ollama_models = MeetingActaSummarizer.get_ollama_models()
    cfg = load_app_config()
    gemini_key = cfg.get('gemini_api_key', '')
    gemini_models = MeetingActaSummarizer.get_gemini_models(gemini_key)
    structured_models = MeetingActaSummarizer.get_structured_models(gemini_key=gemini_key)

    return jsonify({
        "gpu": gpu_info,
        "ollama_online": len(ollama_models) > 0,
        "ollama_models": ollama_models,
        "gemini_configured": bool(gemini_key and gemini_key.strip()),
        "gemini_models": gemini_models,
        "structured_models": structured_models,
        "ai_models": MeetingActaSummarizer.get_available_models(gemini_key=gemini_key)
    })

@app.route('/api/start-ollama', methods=['POST'])
def start_ollama_service():
    """Intenta iniciar el proceso de Ollama si no está corriendo."""
    try:
        subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        time.sleep(1.5)
        models = MeetingActaSummarizer.get_ollama_models()
        return jsonify({"success": len(models) > 0, "models": models})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Lee o actualiza la configuración persistente."""
    if request.method == 'GET':
        return jsonify(load_app_config())
    else:
        new_cfg = request.get_json() or {}
        current = load_app_config()
        current.update(new_cfg)
        if save_app_config(current):
            return jsonify({"success": True, "config": current})
        return jsonify({"success": False, "error": "No se pudo guardar la configuración"}), 500

@app.route('/api/gemini/test', methods=['POST'])
def test_gemini_key():
    """Prueba la validez de la API Key de Google Gemini en Google AI Studio."""
    data = request.get_json() or {}
    key = data.get('api_key', '').strip()
    if not key:
        return jsonify({"success": False, "error": "La clave API está vacía"}), 400

    models = MeetingActaSummarizer.get_gemini_models(api_key=key)
    if models:
        return jsonify({
            "success": True,
            "message": f"Conexión exitosa con Google AI Studio. {len(models)} modelos detectados.",
            "models": models
        })
    else:
        return jsonify({
            "success": False,
            "error": "Clave API inválida o sin cuota de acceso a Google AI Studio."
        }), 400

@app.route('/api/transcribe', methods=['POST'])
def start_transcription():
    """Inicia la transcripción desde un archivo multimedia local."""
    global current_task
    with task_lock:
        if current_task["status"] in ["converting", "transcribing", "diarizing", "saving"]:
            return jsonify({"error": "Ya hay una tarea en ejecución."}), 409

    if 'file' not in request.files:
        return jsonify({"error": "No se ha proporcionado ningún archivo multimedia."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Archivo no seleccionado."}), 400

    original_filename = secure_filename(file.filename) or "audio_sesion.mp3"
    temp_path = os.path.join(UPLOAD_FOLDER, f"upload_{int(time.time())}_{original_filename}")
    file.save(temp_path)

    model_name = request.form.get('model', 'large-v3-turbo')
    language = request.form.get('language', 'auto')
    project_name = request.form.get('project', 'General')
    custom_name = request.form.get('custom_name', '')
    formats = request.form.getlist('formats') or ['txt', 'srt', 'vtt']

    with task_lock:
        current_task = {
            "status": "converting",
            "progress": 5,
            "step_detail": "Recibiendo archivo e inicializando motor...",
            "device_info": "GPU NVIDIA RTX 4070 Activa",
            "result": None,
            "error": None,
            "start_time": time.time()
        }

    t = threading.Thread(
        target=async_transcription_worker,
        args=(temp_path, original_filename, model_name, language, formats, project_name, custom_name),
        daemon=True
    )
    t.start()

    return jsonify({"success": True, "message": "Transcripción iniciada con éxito."})

@app.route('/api/youtube', methods=['POST'])
def process_youtube():
    """Descarga audio desde un enlace de YouTube e inicia la transcripción."""
    global current_task
    with task_lock:
        if current_task["status"] in ["converting", "transcribing", "diarizing", "saving"]:
            return jsonify({"error": "Ya hay una tarea en ejecución."}), 409

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({"error": "Enlace de YouTube no proporcionado."}), 400

    model_name = data.get('model', 'large-v3-turbo')
    language = data.get('language', 'auto')
    project_name = data.get('project', 'General')
    custom_name = data.get('custom_name', '')

    with task_lock:
        current_task = {
            "status": "converting",
            "progress": 5,
            "step_detail": "Extrayendo audio directamente desde YouTube...",
            "device_info": "GPU NVIDIA RTX 4070 Activa",
            "result": None,
            "error": None,
            "start_time": time.time()
        }

    def yt_worker():
        try:
            audio_path, yt_title = YouTubeAudioExtractor.download_audio(url, UPLOAD_FOLDER)
            async_transcription_worker(
                audio_path,
                f"{yt_title}.mp3",
                model_name,
                language,
                ['txt', 'srt', 'vtt'],
                project_name,
                custom_name or yt_title
            )
        except Exception as e:
            with task_lock:
                current_task["status"] = "error"
                current_task["error"] = f"Error al procesar YouTube: {str(e)}"
                current_task["step_detail"] = f"Fallo al descargar YouTube: {str(e)}"

    t = threading.Thread(target=yt_worker, daemon=True)
    t.start()

    return jsonify({"success": True, "message": "Extracción de YouTube iniciada."})

@app.route('/api/summarize_stream', methods=['POST'])
def summarize_stream():
    """Genera el Acta Oficial transmitiendo tokens en tiempo real mediante Server-Sent Events (SSE)."""
    data = request.get_json() or {}
    transcript = data.get('text', '')
    title = data.get('title', 'Reunión de Trabajo')
    duration = data.get('duration', 'N/A')
    model = data.get('model', 'qwen2.5:7b')
    session_id = data.get('session_id', '')

    if not transcript:
        return jsonify({"error": "Falta el texto de transcripción"}), 400

    cfg = load_app_config()
    gemini_key = cfg.get('gemini_api_key', '')

    def event_stream():
        accumulated_summary = []
        try:
            if "Gemini" in model or "gemini" in model.lower():
                for chunk in MeetingActaSummarizer.stream_summary_gemini(
                    transcript, title=title, duration=duration, model_name=model, api_key=gemini_key
                ):
                    if chunk.get('token'):
                        accumulated_summary.append(chunk['token'])
                    yield f"data: {json.dumps(chunk)}\n\n"
            elif "Offline" in model or "Heurístico" in model or "Desconectado" in model:
                acta = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration)
                accumulated_summary.append(acta)
                yield f"data: {json.dumps({'token': acta, 'done': True})}\n\n"
            else:
                for chunk in MeetingActaSummarizer.stream_summary_ollama(
                    transcript, title=title, duration=duration, model=model
                ):
                    if chunk.get('token'):
                        accumulated_summary.append(chunk['token'])
                    yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            fallback = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration)
            accumulated_summary.append(fallback)
            err_msg = f"> ⚠️ Error inesperado: {str(e)}\n\n" + fallback
            yield f"data: {json.dumps({'token': err_msg, 'done': True})}\n\n"
        finally:
            if session_id and accumulated_summary:
                try:
                    full_text = "".join(accumulated_summary)
                    is_cloud = bool("Gemini" in model or "gemini" in model.lower())
                    engine_type = "cloud" if is_cloud else "local"
                    db.update_summary(session_id, full_text, engine=engine_type, model_name=model)
                except Exception:
                    pass

    res = Response(stream_with_context(event_stream()), mimetype='text/event-stream')
    res.headers['Cache-Control'] = 'no-cache, no-transform'
    res.headers['X-Accel-Buffering'] = 'no'
    res.headers['Connection'] = 'keep-alive'
    return res

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """Obtiene el historial estructurado completo desde la base de datos SQLite instantáneamente."""
    project = request.args.get('project', '')
    search = request.args.get('search', '')
    sessions = db.list_sessions(project=project, search=search)
    return jsonify({"sessions": sessions})

@app.route('/api/session/<session_id>', methods=['GET', 'DELETE'])
def handle_session(session_id):
    """Obtiene o elimina una sesión por su ID."""
    if request.method == 'GET':
        sess = db.get_session(session_id)
        if sess:
            return jsonify(sess)
        return jsonify({"error": "Sesión no encontrada"}), 404
    else:
        success = db.delete_session(session_id)
        return jsonify({"success": success})

@app.route('/api/export/docx', methods=['POST'])
def export_docx():
    """Exporta el Acta Oficial a formato Microsoft Word (.docx) descargable."""
    data = request.get_json() or {}
    markdown_text = data.get('markdown', '')
    title = data.get('title', 'Acta Oficial de Sesión')

    if not markdown_text:
        return jsonify({"error": "No hay texto para exportar"}), 400

    try:
        buffer = MeetingMinutesExporter.generate_docx(markdown_text, title=title)
        filename = f"{re.sub(r'[^\\w\\-_\\. ]', '_', title).strip() or 'Acta_Oficial'}.docx"
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": f"Error generando documento Word: {str(e)}"}), 500

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    """Exporta el Acta Oficial a formato PDF descargable."""
    data = request.get_json() or {}
    markdown_text = data.get('markdown', '')
    title = data.get('title', 'Acta Oficial de Sesión')

    if not markdown_text:
        return jsonify({"error": "No hay texto para exportar"}), 400

    try:
        buffer = MeetingMinutesExporter.generate_pdf(markdown_text, title=title)
        filename = f"{re.sub(r'[^\\w\\-_\\. ]', '_', title).strip() or 'Acta_Oficial'}.pdf"
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": f"Error generando documento PDF: {str(e)}"}), 500

if __name__ == '__main__':
    print("Iniciando WhisperDesk Studio Pro en http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
