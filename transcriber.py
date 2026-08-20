import os
import gc
import subprocess
import math
import torch
from faster_whisper import WhisperModel
from diarizer import SpeakerDiarizer

class VideoConverter:
    """Clase de alto rendimiento para convertir videos a audio usando FFmpeg multihilo con progreso en vivo."""
    
    SUPPORTED_FORMATS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    
    @staticmethod
    def convert(input_path, output_path=None, progress_callback=None):
        """Convierte un archivo de video a audio WAV 16kHz usando FFmpeg multihilo."""
        if not output_path:
            output_path = os.path.splitext(input_path)[0] + '.wav'

        duration = VideoConverter.get_media_info(input_path).get('duration', 0.0)

        command = [
            'ffmpeg',
            '-y',
            '-threads', '0',
            '-i', input_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1'
        ]

        if progress_callback and duration > 0:
            command.extend(['-progress', 'pipe:1', '-nostats'])

        command.append(output_path)
        
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            if progress_callback and duration > 0:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creationflags,
                    text=True,
                    bufsize=1
                )
                for line in process.stdout:
                    if 'out_time_us=' in line or 'out_time_ms=' in line:
                        try:
                            val_str = line.split('=')[1].strip()
                            if val_str and val_str.isdigit():
                                current_sec = int(val_str) / 1000000.0 if 'out_time_us' in line else int(val_str) / 1000.0
                                pct = min(100.0, (current_sec / duration) * 100.0)
                                progress_callback(current_sec, duration, pct)
                        except Exception:
                            pass
                process.wait()
                if process.returncode != 0:
                    err = process.stderr.read()
                    raise Exception(f"Error en FFmpeg: {err}")
            else:
                subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
                
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error al convertir video: {e.stderr.decode('utf-8', errors='ignore')}")
            
    @staticmethod
    def get_media_info(file_path):
        """Obtiene la duración del archivo usando ffprobe."""
        command = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
            duration = float(result.stdout.decode().strip())
            return {"duration": duration}
        except (subprocess.CalledProcessError, ValueError):
            return {"duration": 0.0}

class WhisperTranscriber:
    """Clase principal para transcribir usando faster-whisper con diarización de alta fidelidad."""
    
    def __init__(self):
        self.model = None
        self.current_model_name = None
        
    def load_model(self, model_name, device=None, compute_type=None):
        """Carga el modelo Whisper con purga previa de VRAM y auto-detección segura de CUDA."""
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if compute_type is None:
            compute_type = 'float16' if device == 'cuda' else 'int8'
            
        if self.current_model_name != model_name or self.model is None:
            if self.model is not None:
                del self.model
                self.model = None
                WhisperTranscriber.purge_vram()
                
            try:
                self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
            except Exception as e:
                if device == 'cuda':
                    WhisperTranscriber.purge_vram()
                    self.model = WhisperModel(model_name, device='cpu', compute_type='int8')
                else:
                    raise e
            self.current_model_name = model_name
            
    def transcribe(self, audio_path, language=None, task='transcribe', progress_callback=None, cancel_event=None):
        """Transcribe un archivo de audio y emite progreso de forma eficiente."""
        if self.model is None:
            raise Exception("El modelo no está cargado. Llama a load_model primero.")
            
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False
        )
        
        total_duration = info.duration
        detected_language = info.language
        
        result_parts = []
        result_segments = []
        
        for segment in segments:
            if cancel_event and cancel_event.is_set():
                break
                
            text = segment.text.strip()
            if text:
                result_segments.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': text
                })
                result_parts.append(text)
                
            if progress_callback:
                try:
                    progress_callback(segment.end, total_duration, text)
                except TypeError:
                    try:
                        progress_callback(segment.end, total_duration, text, " ".join(result_parts))
                    except Exception:
                        pass
                        
        # Aplicar diarización de hablantes e inferencia de nombres
        diarized_segments = SpeakerDiarizer.perform_diarization(result_segments)
        speaker_text = SpeakerDiarizer.format_transcript_with_speakers(diarized_segments)
        clean_text = WhisperTranscriber.format_as_clean_paragraphs(result_segments)
        
        # Purga ligera de cache VRAM
        WhisperTranscriber.purge_vram()
                
        return {
            "text": clean_text,
            "plain_text": clean_text,
            "speaker_text": speaker_text,
            "segments": diarized_segments,
            "language": detected_language,
            "duration": total_duration,
            "cancelled": bool(cancel_event and cancel_event.is_set())
        }

    @staticmethod
    def format_as_clean_paragraphs(segments):
        """Genera párrafos limpios y continuos de lectura natural sin marcas repetitivas ni timestamps."""
        if not segments:
            return ""
        
        paragraphs = []
        current_p = []
        
        for seg in segments:
            text = seg.get('text', '').strip()
            if not text:
                continue
            current_p.append(text)
            # Agrupar en párrafos naturales cada 4-6 oraciones o cuando termina en punto
            if len(current_p) >= 5 or (len(current_p) >= 3 and text.endswith(('.', '!', '?'))):
                paragraphs.append(" ".join(current_p))
                current_p = []
                
        if current_p:
            paragraphs.append(" ".join(current_p))
            
        return "\n\n".join(paragraphs)

    @staticmethod
    def purge_vram():
        """Purga el caché de PyTorch CUDA y fuerza la recolección de basura de Python."""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
        except Exception:
            pass
        
    @staticmethod
    def format_as_txt(result):
        """Formatea como texto plano."""
        return result['text']
        
    @staticmethod
    def format_time_srt(seconds):
        """Convierte segundos a formato de tiempo SRT (HH:MM:SS,mmm)."""
        hours = math.floor(seconds / 3600)
        minutes = math.floor((seconds % 3600) / 60)
        secs = math.floor(seconds % 60)
        msecs = math.floor((seconds - math.floor(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"
        
    @staticmethod
    def format_as_srt(result):
        """Formatea el resultado como archivo SRT con alto rendimiento."""
        parts = []
        for i, segment in enumerate(result.get('segments', []), start=1):
            start_time = WhisperTranscriber.format_time_srt(segment['start'])
            end_time = WhisperTranscriber.format_time_srt(segment['end'])
            parts.append(f"{i}\n{start_time} --> {end_time}\n{segment['text'].strip()}\n\n")
        return "".join(parts)
        
    @staticmethod
    def format_time_vtt(seconds):
        """Convierte segundos a formato de tiempo WebVTT (HH:MM:SS.mmm)."""
        hours = math.floor(seconds / 3600)
        minutes = math.floor((seconds % 3600) / 60)
        secs = math.floor(seconds % 60)
        msecs = math.floor((seconds - math.floor(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{msecs:03d}"
        
    @staticmethod
    def format_as_vtt(result):
        """Formatea el resultado como archivo WebVTT con alto rendimiento."""
        parts = ["WEBVTT\n\n"]
        for i, segment in enumerate(result.get('segments', []), start=1):
            start_time = WhisperTranscriber.format_time_vtt(segment['start'])
            end_time = WhisperTranscriber.format_time_vtt(segment['end'])
            parts.append(f"{i}\n{start_time} --> {end_time}\n{segment['text'].strip()}\n\n")
        return "".join(parts)
        
    @staticmethod
    def get_available_models():
        """Retorna una lista de modelos disponibles."""
        return [
            {"name": "tiny", "size": "39M", "vram_needed": "~1GB"},
            {"name": "base", "size": "74M", "vram_needed": "~1GB"},
            {"name": "small", "size": "244M", "vram_needed": "~2GB"},
            {"name": "medium", "size": "769M", "vram_needed": "~5GB"},
            {"name": "large-v3", "size": "1550M", "vram_needed": "~10GB"},
            {"name": "large-v3-turbo", "size": "809M", "vram_needed": "~6GB"}
        ]
