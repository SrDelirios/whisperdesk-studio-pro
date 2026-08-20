import os
import json
import sqlite3
import time
import re
import urllib.parse
from datetime import datetime

class DatabaseManager:
    """Administrador de base de datos SQLite para sesiones de WhisperDesk Studio Pro."""

    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, 'whisper_sessions.db')
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self):
        """Crea las tablas necesarias si no existen."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    project TEXT DEFAULT 'General',
                    created_at REAL NOT NULL,
                    created_str TEXT NOT NULL,
                    audio_path TEXT,
                    audio_filename TEXT,
                    media_url TEXT,
                    duration REAL DEFAULT 0.0,
                    duration_str TEXT DEFAULT '00:00',
                    language TEXT DEFAULT 'es',
                    model_used TEXT DEFAULT 'large-v3-turbo',
                    plain_text TEXT NOT NULL,
                    speaker_text TEXT NOT NULL,
                    segments_json TEXT NOT NULL,
                    summary TEXT DEFAULT '',
                    file_format TEXT DEFAULT 'txt'
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_project ON sessions(project)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON sessions(created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON sessions(session_id)')
            conn.commit()

    def save_session(self, data):
        """Inserta o actualiza una sesión completa en la base de datos."""
        session_id = data.get('session_id') or f"session_{int(time.time() * 1000)}"
        title = data.get('title') or data.get('custom_name') or 'Sesión de Audio'
        project = data.get('project') or 'General'
        created_at = data.get('created_at', time.time())
        created_str = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M')
        audio_path = data.get('audio_path', '')
        audio_filename = data.get('audio_filename') or (os.path.basename(audio_path) if audio_path else '')
        media_url = data.get('media_url', '')
        duration = float(data.get('duration', 0.0))
        
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins:02d}:{secs:02d}"

        language = data.get('language', 'es')
        model_used = data.get('model_used', 'large-v3-turbo')
        plain_text = data.get('plain_text') or data.get('text', '')
        speaker_text = data.get('speaker_text') or plain_text
        
        segments = data.get('segments', [])
        segments_json = json.dumps(segments, ensure_ascii=False) if isinstance(segments, list) else str(segments)
        summary = data.get('summary', '')
        file_format = data.get('file_format', 'txt')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (
                    session_id, title, project, created_at, created_str,
                    audio_path, audio_filename, media_url, duration, duration_str,
                    language, model_used, plain_text, speaker_text, segments_json,
                    summary, file_format
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    title=excluded.title,
                    project=excluded.project,
                    audio_path=excluded.audio_path,
                    audio_filename=excluded.audio_filename,
                    media_url=excluded.media_url,
                    duration=excluded.duration,
                    duration_str=excluded.duration_str,
                    plain_text=excluded.plain_text,
                    speaker_text=excluded.speaker_text,
                    segments_json=excluded.segments_json,
                    summary=excluded.summary
            ''', (
                session_id, title, project, created_at, created_str,
                audio_path, audio_filename, media_url, duration, duration_str,
                language, model_used, plain_text, speaker_text, segments_json,
                summary, file_format
            ))
            conn.commit()
        return session_id

    def get_session(self, session_id):
        """Recupera una sesión estructurada completa."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sessions WHERE session_id = ? OR title = ? LIMIT 1', (session_id, session_id))
            row = cursor.fetchone()
            if not row:
                return None
            
            d = dict(row)
            try:
                d['segments'] = json.loads(d.get('segments_json', '[]'))
            except Exception:
                d['segments'] = []
            return d

    def list_sessions(self, project=None, search=None):
        """Lista las sesiones ordenadas de más reciente a más antigua."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, session_id, title, project, created_at, created_str, duration, duration_str, audio_filename, media_url, language, model_used, (summary != '') AS has_summary FROM sessions WHERE 1=1"
            params = []

            if project and project != 'General' and project != 'all':
                query += " AND project = ?"
                params.append(project)

            if search and search.strip():
                query += " AND (title LIKE ? OR plain_text LIKE ? OR speaker_text LIKE ?)"
                kw = f"%{search.strip()}%"
                params.extend([kw, kw, kw])

            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def update_summary(self, session_id, summary_text):
        """Actualiza el acta de una sesión."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sessions SET summary = ? WHERE session_id = ? OR title = ?', (summary_text, session_id, session_id))
            conn.commit()

    def delete_session(self, session_id):
        """Elimina una sesión."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE session_id = ? OR title = ?', (session_id, session_id))
            conn.commit()

    def auto_import_txt_files(self, output_folder, upload_folder):
        """Migra automáticamente archivos TXT legacy existentes a la base de datos estructurada."""
        if not os.path.exists(output_folder):
            return

        for root, dirs, files in os.walk(output_folder):
            for file in files:
                if file.endswith('.txt') and file != '.gitkeep':
                    txt_path = os.path.join(root, file)
                    rel_dir = os.path.relpath(root, output_folder)
                    project = 'General' if rel_dir == '.' else rel_dir
                    
                    base_name = os.path.splitext(file)[0]
                    clean_title = re.sub(r'_\d{10}$', '', base_name)
                    session_id = f"session_{base_name}"

                    existing = self.get_session(session_id)
                    if existing:
                        continue

                    try:
                        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                            raw_content = f.read()

                        segments = []
                        plain_paragraphs = []
                        speaker_paragraphs = []
                        
                        pattern = re.compile(r'(?:⏱️|⏱)?\s*(\d+:\d+(?::\d+)?)\s*\[(Hablante\s*\d+|[^\]]+)\]:\s*([\s\S]*?)(?=(?:⏱️|⏱)?\s*\d+:\d+(?::\d+)?\s*\[|$)', re.IGNORECASE)
                        matches = list(pattern.finditer(raw_content))

                        if matches:
                            for m in matches:
                                time_str = m.group(1)
                                spk = m.group(2).strip()
                                txt = m.group(3).strip()
                                
                                parts = [int(p) for p in time_str.split(':')]
                                secs = parts[0]*60 + parts[1] if len(parts) == 2 else parts[0]*3600 + parts[1]*60 + parts[2]
                                
                                segments.append({
                                    "start": secs,
                                    "end": secs + 10,
                                    "speaker": spk,
                                    "text": txt
                                })
                                plain_paragraphs.append(txt)
                                speaker_paragraphs.append(f"⏱️ {time_str} [{spk}]:\n{txt}")
                            
                            plain_text = "\n\n".join(plain_paragraphs)
                            speaker_text = "\n\n".join(speaker_paragraphs)
                        else:
                            plain_text = raw_content
                            speaker_text = raw_content

                        audio_path = ""
                        audio_filename = ""
                        media_url = ""
                        
                        media_exts = ('.wav', '.mp3', '.m4a', '.mp4', '.mkv', '.flac', '.webm', '.ogg')
                        if os.path.exists(upload_folder):
                            for uf in os.listdir(upload_folder):
                                u_base, u_ext = os.path.splitext(uf)
                                if u_ext.lower() in media_exts:
                                    if u_base == base_name or u_base == clean_title or base_name.startswith(u_base) or clean_title.startswith(u_base):
                                        audio_path = os.path.join(upload_folder, uf)
                                        audio_filename = uf
                                        media_url = f"/api/media/{urllib.parse.quote(uf)}"
                                        break

                        seg_duration = segments[-1].get("end", 0.0) if segments else 0.0
                        self.save_session({
                            "session_id": session_id,
                            "title": clean_title,
                            "project": project,
                            "created_at": os.path.getmtime(txt_path),
                            "audio_path": audio_path,
                            "audio_filename": audio_filename,
                            "media_url": media_url,
                            "duration": seg_duration,
                            "plain_text": plain_text,
                            "speaker_text": speaker_text,
                            "segments": segments
                        })
                    except Exception as e:
                        pass
