import os
import re
import json
import requests
import threading

class MeetingActaSummarizer:
    """Generador de Actas Oficiales de Sesión con soporte para Google Gemini (AI Studio) y Ollama Local."""

    ACTA_PROMPT_TEMPLATE = """Eres un asistente ejecutivo senior de nivel directivo y analista experto en sintesis de reuniones corporativas.
Tu objetivo es redactar un Acta Oficial de Sesion exhaustiva, fidedigna, profunda y estructurada en espanol a partir de la transcripcion adjunta.

REGLAS FUNDAMENTALES DE REDACCION:
1. FIDELIDAD Y CONTEXTO REAL: Basa el acta exclusivamente en lo conversado. Identifica y utiliza los nombres reales de los participantes si se presentan o mencionan a lo largo del audio (ej. Gustavo Mejia, Nicolas Ortega, etc.).
2. PROFUNDIDAD EJECUTIVA: Evita generalidades, frases vagas o plantillas vacias. Incluye detalles concretos, cifras, tecnologias, herramientas, acuerdos especificos, problemas analizados y planes de accion reales mencionados en la sesion.
3. ESTRUCTURA Y FORMATO MARKDOWN: Sigue rigurosamente la siguiente estructura:

# ACTA OFICIAL DE SESION: {title}
**Fecha:** {date}  |  **Duracion:** {duration}  |  **Participantes:** {participants}

---

### 1. SINTESIS EJECUTIVA Y CONTEXTO
[Redacta 2 a 4 parrafos detallados explicando con total precision el objetivo central de la sesion, el contexto del proyecto o discusion, los antecedentes analizados y el estado general de las iniciativas tratadas].

### 2. PARTICIPANTES Y ROLES EN LA SESION
- **[Nombre o Hablante]**: [Perfil, rol expuesto o aportes principales realizados durante la sesion].
- **[Nombre o Hablante]**: [Perfil, rol expuesto o aportes principales realizados durante la sesion].

### 3. TEMAS TRATADOS Y DISCUSION DETALLADA
- **[Tema / Bloque 1]**: [Explicacion detallada y profunda de lo conversado, posturas de los participantes, detalles tecnicos, presupuestales o creativos expuestos].
- **[Tema / Bloque 2]**: [Explicacion detallada y profunda de lo conversado...].
- **[Tema / Bloque 3]**: [Explicacion detallada y profunda de lo conversado...].

### 4. ACUERDOS Y DECISIONES CLAVE
- **[Acuerdo 1]**: [Decision concreta tomada y justificacion o consenso alcanzado].
- **[Acuerdo 2]**: [Decision concreta tomada y justificacion o consenso alcanzado].

### 5. MATRIZ DE COMPROMISOS Y RESPONSABILIDADES (ACTION ITEMS)
- [ ] **[Responsable / Encargado]**: [Tarea especifica y accionable] — *Plazo / Fecha tentativa:* [Fecha mencionada o 'Por coordinar'].
- [ ] **[Responsable / Encargado]**: [Tarea especifica y accionable] — *Plazo / Fecha tentativa:* [Fecha mencionada o 'Por coordinar'].

### 6. PUNTOS CRITICOS Y ASUNTOS PENDIENTES
- **[Asunto pendiente 1]**: [Detalle de los puntos que requieren validacion, desembolso, cotizaciones o seguimiento en el proximo encuentro].
- **[Asunto pendiente 2]**: [Detalle de los puntos...].

======================================================================
TRANSCRIPCION COMPLETA DE LA SESION:
{transcript}
"""

    @staticmethod
    def _clean_transcript_text(transcript: str) -> str:
        """Limpia marcas tecnicas para una lectura fluida."""
        if not transcript:
            return ""
        cleaned = re.sub(r'⏱\s*\d+:\d+(?::\d+)?\s*\[.*?\]:\s*', '', transcript)
        cleaned = re.sub(r'\[Hablante\s*\d+.*?\]:\s*', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def _optimize_context_for_ollama(transcript: str, max_chars: int = 15000) -> str:
        """Prepara el contexto para Ollama local optimizando memoria para audios de cualquier duración sin exceder la VRAM."""
        clean = MeetingActaSummarizer._clean_transcript_text(transcript)
        if len(clean) <= max_chars:
            return clean

        lines = [l.strip() for l in clean.split('\n') if l.strip()]
        if not lines:
            return clean[:max_chars]

        # 1. Apertura e introducción (primeros 3500 caracteres)
        head = []
        head_len = 0
        for l in lines:
            head.append(l)
            head_len += len(l)
            if head_len >= 3500:
                break

        # 2. Extractos intermedios con palabras clave de acuerdos, decisiones y compromisos (8000 caracteres)
        action_keywords = [
            'acuerd', 'comprom', 'hacer', 'revis', 'enviar', 'pago', 'entrega', 'mañana',
            'semana', 'tarea', 'responsable', 'decidi', 'conclusi', 'aprob', 'confirm',
            'defin', 'objetivo', 'desembol', 'proyecto', 'presupuesto', 'fase', 'precio',
            'contrato', 'equipo', 'cliente', 'desarrollo', 'tiempo', 'fecha', 'costo',
            'mamut', 'plazo', 'informe', 'taller', 'archivo', 'digitaliz', 'problema',
            'solucion', 'riesgo', 'propuesta', 'cronograma', 'rubro', 'financ'
        ]
        middle = []
        middle_len = 0
        mid_lines = lines[len(head):-30] if len(lines) > 60 else []
        for l in mid_lines:
            if any(k in l.lower() for k in action_keywords):
                middle.append(l)
                middle_len += len(l)
                if middle_len >= 8000:
                    break

        # 3. Cierre y conclusiones (3500 caracteres)
        tail = []
        tail_len = 0
        for l in reversed(lines[-30:]):
            tail.insert(0, l)
            tail_len += len(l)
            if tail_len >= 3500:
                break

        combined_parts = []
        if head:
            combined_parts.append("\n".join(head))
        if middle:
            combined_parts.append("\n--- [DISCUSION DE TEMAS, ACUERDOS Y COMPROMISOS] ---\n" + "\n".join(middle))
        if tail:
            combined_parts.append("\n--- [CONCLUSIONES Y PROXIMOS PASOS] ---\n" + "\n".join(tail))

        result = "\n\n".join(combined_parts)
        return result[:max_chars]

    @staticmethod
    def get_ollama_models(host="http://localhost:11434"):
        """Detecta dinámicamente los modelos instalados en Ollama y retorna sus nombres puros."""
        available = []
        try:
            r = requests.get(f"{host}/api/tags", timeout=2.0)
            if r.status_code == 200:
                models = r.json().get('models', [])
                for m in models:
                    name = m.get('name', '')
                    if name:
                        available.append(name)
        except Exception:
            pass
        return available

    @staticmethod
    def clean_ollama_model_name(raw_name: str, host: str = "http://localhost:11434") -> str:
        """Sanitiza y valida el nombre del modelo contra los modelos instalados en Ollama garantizando que no falle."""
        if not raw_name:
            raw_name = "qwen2.5:7b"
        s = str(raw_name).strip()
        # Eliminar emojis y caracteres decorativos al inicio
        s = re.sub(r'^[^\w\.\:\-]+', '', s)
        # Eliminar prefijos 'Ollama:' o 'ollama:'
        s = re.sub(r'^(?:Ollama:\s*|ollama:\s*)', '', s, flags=re.IGNORECASE)
        # Eliminar sufijos entre paréntesis ej. (Local GPU)
        s = re.sub(r'\s*\([^)]*\).*$', '', s)
        s = re.sub(r'\s*—.*$', '', s)
        clean = s.strip()

        # Validar contra los modelos realmente instalados en Ollama
        installed = MeetingActaSummarizer.get_ollama_models(host=host)
        if installed:
            if clean in installed:
                return clean
            for m in installed:
                if m.lower() == clean.lower():
                    return m
            for m in installed:
                if clean.lower() in m.lower() or m.lower().startswith(clean.lower()):
                    return m
            # Fallback inteligente al modelo instalado más potente
            for preferred in ['qwen2.5:7b', 'llama3.1:8b', 'llama3:latest', 'llama3.2:latest']:
                if preferred in installed:
                    return preferred
            return installed[0]

        return clean or "qwen2.5:7b"

    @staticmethod
    def get_gemini_models_raw(api_key=""):
        """Consulta en tiempo real a Google AI Studio y filtra estrictamente solo los modelos flagship de texto puro."""
        if not api_key or not api_key.strip():
            return []
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}", timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                models = data.get('models', [])
                valid_models = []
                
                # Palabras prohibidas: modelos de audio/música (lyria), imágenes (imagen), embeddings, lite o versiones deprecadas (2.5, 2.0, 1.5)
                exclude_keywords = [
                    'tts', 'image', 'imagen', 'lyria', 'gemma', 'nano-banana', 'embed', 'aqa',
                    'robotics', 'customtools', 'deep-research', 'computer-use', 'antigravity',
                    '2.5', '2.0', '1.5', '1.0', 'lite', 'omni'
                ]

                for m in models:
                    methods = m.get('supportedGenerationMethods', [])
                    name = m.get('name', '').replace('models/', '')
                    low = name.lower()
                    
                    if 'generateContent' not in methods:
                        continue
                    if any(bad in low for bad in exclude_keywords):
                        continue
                        
                    disp_name = m.get('displayName', name)
                    valid_models.append({
                        "id": name,
                        "name": f"{name} ({disp_name})",
                        "display": disp_name
                    })

                # Función de puntuación para ordenar de más reciente/capaz a menor
                def score_model(m):
                    mid = m['id'].lower()
                    if '3.7' in mid: return 100
                    if '3.6' in mid: return 90
                    if '3.1-pro' in mid: return 85
                    if '3-pro' in mid: return 80
                    if '3-flash' in mid: return 75
                    if '3.5-flash' in mid: return 70
                    if 'flash-latest' in mid: return 65
                    if 'pro-latest' in mid: return 60
                    return 10

                valid_models.sort(key=score_model, reverse=True)
                return valid_models
        except Exception:
            pass

        return [
            {"id": "gemini-3.7-flash", "name": "gemini-3.7-flash (Gemini 3.7 Flash)", "display": "Gemini 3.7 Flash"},
            {"id": "gemini-3.6-flash", "name": "gemini-3.6-flash (Gemini 3.6 Flash)", "display": "Gemini 3.6 Flash"},
            {"id": "gemini-3.1-pro-preview", "name": "gemini-3.1-pro-preview (Gemini 3.1 Pro Preview)", "display": "Gemini 3.1 Pro Preview"},
            {"id": "gemini-3-flash-preview", "name": "gemini-3-flash-preview (Gemini 3 Flash Preview)", "display": "Gemini 3 Flash Preview"},
            {"id": "gemini-flash-latest", "name": "gemini-flash-latest (Gemini Flash Latest)", "display": "Gemini Flash Latest"},
            {"id": "gemini-pro-latest", "name": "gemini-pro-latest (Gemini Pro Latest)", "display": "Gemini Pro Latest"}
        ]

    @staticmethod
    def get_gemini_models(api_key=""):
        """Lista plana de modelos Gemini válidos."""
        raw = MeetingActaSummarizer.get_gemini_models_raw(api_key=api_key)
        return [m['name'] for m in raw]

    @staticmethod
    def get_structured_models(ollama_host="http://localhost:11434", gemini_key=""):
        """Retorna los modelos organizados con valores puros de ID sin emojis."""
        recommended = []
        cloud_other = []
        local_models = []

        # 1. Google Gemini Flagship Models
        if gemini_key and gemini_key.strip():
            raw_gemini = MeetingActaSummarizer.get_gemini_models_raw(api_key=gemini_key)
            for m in raw_gemini:
                recommended.append({
                    "value": m['id'],
                    "label": f"{m['display']} (Google AI Studio)",
                    "is_recommended": True
                })

        # 2. Ollama Local Models
        ollama_raw = MeetingActaSummarizer.get_ollama_models(host=ollama_host)
        for om in ollama_raw:
            is_rec_local = any(k in om.lower() for k in ['qwen2.5:7b', 'llama3.1', 'llama3.3', 'llama3:latest'])
            if is_rec_local:
                recommended.append({
                    "value": om,
                    "label": f"{om} (Local GPU)",
                    "is_recommended": True
                })
            else:
                local_models.append({
                    "value": om,
                    "label": f"{om} (Local)"
                })

        return {
            "recommended": recommended,
            "cloud_other": cloud_other,
            "local_models": local_models,
            "offline": [{"value": "Resumen Heuristico Offline", "label": "Resumen Heurístico (Offline)"}]
        }

    @staticmethod
    def get_available_models(ollama_host="http://localhost:11434", gemini_key=""):
        """Lista consolidada plana para compatibilidad."""
        structured = MeetingActaSummarizer.get_structured_models(ollama_host=ollama_host, gemini_key=gemini_key)
        flat = []
        for item in structured.get('recommended', []):
            flat.append(item['value'])
        for item in structured.get('cloud_other', []):
            flat.append(item['value'])
        for item in structured.get('local_models', []):
            flat.append(item['value'])
        if not flat and not (gemini_key and gemini_key.strip()):
            flat.append("Ollama Desconectado (Configura Gemini en Ajustes)")
        flat.append("Resumen Heuristico Offline")
        return flat

    # =========================================================================
    # GOOGLE GEMINI API ENGINE (GOOGLE AI STUDIO)
    # =========================================================================
    @staticmethod
    def stream_summary_gemini(transcript: str, title: str = "Reunion", duration: str = "N/A",
                              participants: str = "Hablantes detectados",
                              model_name: str = "gemini-flash-latest", api_key: str = ""):
        """Genera el Acta Oficial transmitiendo tokens en tiempo real desde Google Gemini API."""
        if not api_key or not api_key.strip():
            yield {"token": "Se requiere una API Key de Google Gemini. Configúrala en la pestaña de Ajustes.", "done": True}
            return

        if not transcript or not transcript.strip():
            yield {"token": "La transcripción está vacía.", "done": True}
            return

        clean_model = model_name.replace("✨", "").replace("⭐", "").replace("☁️", "").strip()
        if "(" in clean_model:
            clean_model = clean_model.split("(")[0].strip()
        if "—" in clean_model:
            clean_model = clean_model.split("—")[0].strip()
        if "/" in clean_model:
            clean_model = clean_model.split("/")[-1].strip()
        if not clean_model:
            clean_model = "gemini-flash-latest"

        prompt = MeetingActaSummarizer.ACTA_PROMPT_TEMPLATE.format(
            title=title,
            date="Hoy",
            duration=duration,
            participants=participants,
            transcript=transcript.strip()
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:streamGenerateContent?alt=sse&key={api_key.strip()}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
            }
        }

        try:
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=(15, 180))
            if r.status_code != 200:
                err_text = r.text
                try:
                    err_json = r.json()
                    err_text = err_json.get('error', {}).get('message', r.text)
                except Exception:
                    pass
                yield {"token": f"Error de Gemini API ({r.status_code}): {err_text}", "done": True}
                return

            has_tokens = False
            for raw_line in r.iter_lines(chunk_size=1):
                if not raw_line:
                    continue
                line = raw_line.decode('utf-8', errors='ignore').strip()
                if line.startswith('data:'):
                    raw_json = line[5:].strip()
                    try:
                        chunk = json.loads(raw_json)
                        candidates = chunk.get('candidates', [])
                        if candidates and 'content' in candidates[0]:
                            parts = candidates[0]['content'].get('parts', [])
                            for p in parts:
                                t = p.get('text', '')
                                if t:
                                    has_tokens = True
                                    yield {"token": t, "done": False}
                    except Exception:
                        pass

            if not has_tokens:
                yield {"token": "No se recibieron datos de Gemini API.", "done": True}
            else:
                yield {"token": "", "done": True}

        except Exception as e:
            yield {"token": f"Error de conexión con Gemini: {str(e)}", "done": True}

    # =========================================================================
    # OLLAMA LOCAL ENGINE
    # =========================================================================
    @staticmethod
    def stream_summary_ollama(transcript: str, title: str = "Reunion", duration: str = "N/A",
                             participants: str = "Hablantes detectados",
                             model: str = "llama3:latest", host: str = "http://localhost:11434"):
        """Genera el Acta Oficial con Ollama transmitiendo tokens con timeout amplio y soporte de modelos locales."""
        clean_model = MeetingActaSummarizer.clean_ollama_model_name(model, host=host)
        optimized_text = MeetingActaSummarizer._optimize_context_for_ollama(transcript)

        if not optimized_text:
            yield {"token": "La transcripción está vacía.", "done": True}
            return

        prompt = MeetingActaSummarizer.ACTA_PROMPT_TEMPLATE.format(
            title=title,
            date="Hoy",
            duration=duration,
            participants=participants,
            transcript=optimized_text
        )

        has_streamed_any = False
        error_msg = None

        try:
            # Conexión rápida y streaming continuo con persistencia en memoria
            r = requests.post(
                f"{host}/api/generate",
                json={
                    "model": clean_model,
                    "prompt": prompt,
                    "stream": True,
                    "keep_alive": "60m",
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                        "num_predict": 2048
                    }
                },
                stream=True,
                timeout=(15, 180)
            )

            if r.status_code == 200:
                for line in r.iter_lines(chunk_size=1):
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8', errors='ignore'))
                            token = chunk.get('response', '')
                            done = chunk.get('done', False)

                            if token:
                                has_streamed_any = True
                                yield {"token": token, "done": done}

                            if done:
                                return
                        except Exception:
                            pass
            else:
                error_msg = f"Ollama respondió con código {r.status_code}: {r.text[:200]}"

        except Exception as e:
            error_msg = f"No se pudo comunicar con Ollama ({clean_model}): {str(e)}"

        # Si falló Ollama, notificar y ofrecer fallback ejecutivo limpio sin emojis ni literales \n
        if not has_streamed_any:
            fallback = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration, participants=participants)
            clean_notice = ""
            if error_msg:
                if "timeout" in str(error_msg).lower():
                    clean_notice = f"> Nota: El modelo local ({clean_model}) tardó demasiado tiempo en procesar esta sesión extensa. Se presenta el acta ejecutiva estructurada de respaldo.\n\n"
                else:
                    clean_notice = f"> Nota: No se pudo comunicar con el modelo local ({clean_model}). Se presenta el acta ejecutiva estructurada.\n\n"
            
            yield {"token": clean_notice + fallback, "done": True}

    @staticmethod
    def generate_heuristic_summary(transcript: str, title: str = "Reunion", duration: str = "N/A", participants: str = "Hablantes detectados"):
        """Generador heurístico offline de emergencia."""
        clean_text = MeetingActaSummarizer._clean_transcript_text(transcript)
        lines = [line.strip() for line in clean_text.split('\n') if line.strip() and len(line.strip()) > 15]

        action_keywords = ['acuerd', 'compromet', 'hacer', 'revisar', 'enviar', 'pago', 'entrega', 'mañana', 'semana', 'lanzar', 'tarea', 'responsable', 'fase']
        decision_keywords = ['quedam', 'decidi', 'conclusi', 'aprob', 'confirm', 'defin', 'presenta', 'acordamos', 'objetivo', 'vamos']

        actions = []
        decisions = []

        for line in lines:
            line_lower = line.lower()
            if any(k in line_lower for k in action_keywords) and len(line) < 220:
                actions.append(line)
            elif any(k in line_lower for k in decision_keywords) and len(line) < 220:
                decisions.append(line)

        overview_text = ""
        if lines:
            first_chunks = lines[:6]
            overview_text = " ".join(first_chunks)
            if len(overview_text) > 400:
                overview_text = overview_text[:400] + "..."
        else:
            overview_text = "Sesión de trabajo y seguimiento de actividades generales del proyecto."

        acta_text = f"""# ACTA EJECUTIVA DE SESION (MODO OFFLINE): {title}
**Fecha:** Hoy  |  **Duracion:** {duration}  |  **Participantes:** {participants}

---

### 1. SINTESIS EJECUTIVA
{overview_text}

---

### 2. ACUERDOS Y DECISIONES PRINCIPALES
"""
        if decisions:
            for d in decisions[:6]:
                acta_text += f"- {d}\n"
        else:
            acta_text += "- Se revisaron los avances principales y la continuidad de las actividades planteadas.\n"
            acta_text += "- Se acordó mantener seguimiento continuo sobre los entregables del proyecto.\n"

        acta_text += "\n### 3. COMPROMISOS Y TAREAS ASIGNADAS (ACTION ITEMS)\n"
        if actions:
            for a in actions[:8]:
                acta_text += f"- [ ] {a}\n"
        else:
            acta_text += "- [ ] **Equipo**: Revisar puntos presentados en la sesión y coordinar próximos entregables.\n"
            acta_text += "- [ ] **Coordinación**: Confirmar calendario de entregas y requerimientos pendientes.\n"

        acta_text += """
---

### 4. PUNTOS CRITICOS Y ASUNTOS PENDIENTES
- Confirmar agenda y fecha para la próxima sesión de revisión.
- Validar requerimientos técnicos y documentación correspondiente.
"""
        return acta_text
