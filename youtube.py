import os
import time
import re
import yt_dlp

class YouTubeAudioExtractor:
    """Extrae audio de URLs de YouTube a alta velocidad con tolerancia total a restricciones de YouTube."""

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """Verifica si la cadena es una URL válida de YouTube (incluyendo shorts, youtu.be, live, etc.)."""
        if not url:
            return False
        pattern = r'(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|v/|shorts/|live/)?([a-zA-Z0-9_-]{11})'
        return bool(re.search(pattern, url.strip()))

    @staticmethod
    def _get_opts(output_template=None) -> dict:
        """Opciones de yt-dlp con player_client adaptativo para evitar el error HTTP 403 de YouTube."""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'format': 'bestaudio/best',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
            }
        }
        if output_template:
            opts.update({
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'postprocessor_args': [
                    '-ar', '16000',
                    '-ac', '1'
                ]
            })
        return opts

    @staticmethod
    def get_video_info(url: str) -> dict:
        """Obtiene metadatos del video sin descargarlo."""
        opts = YouTubeAudioExtractor._get_opts()
        opts['extract_flat'] = True
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get('title', 'Video de YouTube'),
                    "duration": info.get('duration', 0),
                    "uploader": info.get('uploader', 'Desconocido'),
                    "id": info.get('id', '')
                }
        except Exception:
            return {"title": "YouTube Video", "duration": 0}

    @staticmethod
    def download_audio(url: str, output_folder: str) -> dict:
        """Descarga el audio de YouTube de forma confiable y rápida convirtiéndolo a WAV 16kHz mono."""
        os.makedirs(output_folder, exist_ok=True)
        timestamp = int(time.time())
        output_template = os.path.join(output_folder, f"yt_{timestamp}.%(ext)s")
        
        opts = YouTubeAudioExtractor._get_opts(output_template)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', f"youtube_{timestamp}")
                duration = info.get('duration', 0)
                
                expected_wav = os.path.join(output_folder, f"yt_{timestamp}.wav")
                
                if not os.path.exists(expected_wav):
                    for f in os.listdir(output_folder):
                        if f.startswith(f"yt_{timestamp}") and f.endswith(".wav"):
                            expected_wav = os.path.join(output_folder, f)
                            break
                            
                return {
                    "audio_path": expected_wav,
                    "title": title,
                    "duration": duration,
                    "url": url
                }
        except Exception as e:
            # Reintento con cliente android exclusivo si falló
            try:
                opts['extractor_args']['youtube']['player_client'] = ['android']
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', f"youtube_{timestamp}")
                    duration = info.get('duration', 0)
                    expected_wav = os.path.join(output_folder, f"yt_{timestamp}.wav")
                    return {
                        "audio_path": expected_wav,
                        "title": title,
                        "duration": duration,
                        "url": url
                    }
            except Exception as e2:
                raise Exception(f"No se pudo descargar el audio del video de YouTube: {str(e2)}")
