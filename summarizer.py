import os
import re
import json
import requests
import threading

class MeetingActaSummarizer:
    """Generador de Actas Oficiales de Sesión con soporte para Google Gemini (AI Studio) y Ollama Local."""

    ACTA_PROMPT_TEMPLATE = """Eres un asistente ejecutivo senior de nivel directivo y analista experto en síntesis de reuniones corporativas.
Tu objetivo es redactar un Acta Oficial de Sesión exhaustiva, fidedigna, profunda y estructurada en español a partir de la transcripción adjunta.

REGLAS FUNDAMENTALES DE REDACCIÓN:
1. FIDELIDAD Y CONTEXTO REAL: Basa el acta exclusivamente en lo conversado. Identifica y utiliza los nombres reales de los participantes si se presentan o mencionan a lo largo del audio (ej. Gustavo Mejía, Nicolás Ortega, etc.).
2. PROFUNDIDAD EJECUTIVA: Evita generalidades, frases vagas o plantillas vacías. Incluye detalles concretos, cifras, tecnologías, herramientas, acuerdos específicos, problemas analizados y planes de acción reales mencionados en la sesión.
3. ESTRUCTURA Y FORMATO MARKDOWN: Sigue rigurosamente la siguiente estructura:

# 📜 ACTA OFICIAL DE SESIÓN: {title}
**Fecha:** {date}  |  **Duración:** {duration}  |  **Participantes Identificados:** {participants}

---

### 📌 1. SÍNTESIS EJECUTIVA & PROPÓSITO DE LA REUNIÓN
[Redacta 2 a 4 párrafos detallados explicando con total precisión el objetivo central de la sesión, el contexto del proyecto o discusión, los antecedentes analizados y el estado general de las iniciativas tratadas].

### 👥 2. PARTICIPANTES Y ROLES EN LA SESIÓN
- **[Nombre o Hablante]**: [Perfil, rol expuesto o aportes principales realizados durante la sesión].
- **[Nombre o Hablante]**: [Perfil, rol expuesto o aportes principales realizados durante la sesión].

### 📋 3. TEMAS TRATADOS Y DISCUSIÓN DETALLADA (ORDEN CRONOLÓGICO)
- **[Tema / Bloque 1]**: [Explicación detallada y profunda de lo conversado, posturas de los participantes, detalles técnicos, presupuestales o creativos expuestos].
- **[Tema / Bloque 2]**: [Explicación detallada y profunda de lo conversado...].
- **[Tema / Bloque 3]**: [Explicación detallada y profunda de lo conversado...].

### 🎯 4. ACUERDOS Y DECISIONES CLAVE
- **[Acuerdo 1]**: [Decisión concreta tomada y justificación o consenso alcanzado].
- **[Acuerdo 2]**: [Decisión concreta tomada y justificación o consenso alcanzado].

### ✅ 5. MATRIZ DE COMPROMISOS Y PRÓXIMAS TAREAS (ACTION ITEMS)
- [ ] **[Responsable / Encargado]**: [Tarea específica y accionable] — *Plazo / Fecha tentativa:* [Fecha mencionada o 'Por coordinar'].
- [ ] **[Responsable / Encargado]**: [Tarea específica y accionable] — *Plazo / Fecha tentativa:* [Fecha mencionada o 'Por coordinar'].

### 💡 6. PUNTOS CRÍTICOS, DUDAS Y TEMAS PENDIENTES
- **[Asunto pendiente / Duda 1]**: [Detalle de los puntos que requieren validación, desembolso, cotizaciones o seguimiento en el próximo encuentro].
- **[Asunto pendiente / Duda 2]**: [Detalle de los puntos...].

======================================================================
TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{transcript}
"""

    @staticmethod
    def _clean_transcript_text(transcript: str) -> str:
        """Limpia marcas técnicas para una lectura fluida."""
        if not transcript:
            return ""
        cleaned = re.sub(r'⏱\s*\d+:\d+(?::\d+)?\s*\[.*?\]:\s*', '', transcript)
        cleaned = re.sub(r'\[Hablante\s*\d+.*?\]:\s*', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def _optimize_context_for_ollama(transcript: str, max_chars: int = 40000) -> str:
        """Prepara el contexto para Ollama local optimizando memoria sin perder partes vitales."""
        clean = transcript.strip()
        if len(clean) <= max_chars:
            return clean

        lines = [l.strip() for l in clean.split('\n') if l.strip()]
        if not lines:
            return clean[:max_chars]

        # 1. Apertura e introducción (primeros 8000 caracteres)
        head = []
        head_len = 0
        for l in lines:
            head.append(l)
            head_len += len(l)
            if head_len >= 8000:
                break

        # 2. Extractos intermedios con palabras de acción, compromisos y decisiones (~22000 caracteres)
        action_keywords = [
            'acuerd', 'comprom', 'hacer', 'revis', 'enviar', 'pago', 'entrega', 'mañana',
            'semana', 'tarea', 'responsable', 'decidi', 'conclusi', 'aprob', 'confirm',
            'defin', 'objetivo', 'desembol', 'proyecto', 'presupuesto', 'fase', 'precio',
            'contrato', 'equipo', 'cliente', 'desarrollo', 'tiempo', 'fecha'
        ]
        middle = []
        middle_len = 0
        mid_lines = lines[len(head):-50] if len(lines) > 100 else []
        for l in mid_lines:
            if any(k in l.lower() for k in action_keywords):
                middle.append(l)
                middle_len += len(l)
                if middle_len >= 22000:
                    break

        # 3. Cierre y conclusiones (~10000 caracteres)
        tail = []
        tail_len = 0
        for l in reversed(lines[-50:]):
            tail.insert(0, l)
            tail_len += len(l)
            if tail_len >= 10000:
                break

        combined_parts = []
        if head:
            combined_parts.append("\n".join(head))
        if middle:
            combined_parts.append("\n--- [DISCUSIÓN DE TEMAS, ACUERDOS Y COMPROMISOS] ---\n" + "\n".join(middle))
        if tail:
            combined_parts.append("\n--- [CONCLUSIONES Y PRÓXIMOS PASOS] ---\n" + "\n".join(tail))

        result = "\n\n".join(combined_parts)
        return result[:max_chars]

    @staticmethod
    def get_ollama_models(host="http://localhost:11434"):
        """Detecta dinámicamente los modelos instalados en Ollama."""
        available = []
        try:
            r = requests.get(f"{host}/api/tags", timeout=2.0)
            if r.status_code == 200:
                models = r.json().get('models', [])
                for m in models:
                    available.append(f"Ollama: {m['name']}")
        except Exception:
            pass
        return available

    @staticmethod
    def get_available_models(ollama_host="http://localhost:11434", gemini_key=""):
        """Lista consolidada de todos los motores de IA disponibles (Gemini + Ollama + Offline)."""
        available = []

        # Modelos de Google Gemini (Google AI Studio)
        if gemini_key and gemini_key.strip():
            available.append("✨ Gemini 2.0 Flash (Google AI Studio - 1M Contexto)")
            available.append("✨ Gemini 1.5 Flash (Google AI Studio - 1M Contexto)")
            available.append("✨ Gemini 1.5 Pro (Google AI Studio - 2M Contexto)")

        # Modelos locales de Ollama
        ollama_models = MeetingActaSummarizer.get_ollama_models(host=ollama_host)
        if ollama_models:
            available.extend(ollama_models)
        else:
            if not (gemini_key and gemini_key.strip()):
                available.append("⚠️ Ollama Desconectado (Configura Gemini en Ajustes)")

        available.append("📝 Resumen Heurístico Offline")
        return available

    # =========================================================================
    # GOOGLE GEMINI API ENGINE (GOOGLE AI STUDIO)
    # =========================================================================
    @staticmethod
    def stream_summary_gemini(transcript: str, title: str = "Reunión", duration: str = "N/A",
                              participants: str = "Hablantes detectados",
                              model_name: str = "gemini-2.0-flash", api_key: str = ""):
        """Genera el Acta Oficial transmitiendo tokens en tiempo real desde Google Gemini API."""
        if not api_key or not api_key.strip():
            yield {"token": "❌ Se requiere una API Key de Google Gemini. Configúrala en la pestaña de Ajustes.", "done": True}
            return

        if not transcript or not transcript.strip():
            yield {"token": "⚠️ La transcripción está vacía.", "done": True}
            return

        # Limpieza de nombre de modelo
        clean_model = "gemini-2.0-flash"
        if "1.5 Pro" in model_name or "gemini-1.5-pro" in model_name:
            clean_model = "gemini-1.5-pro"
        elif "1.5 Flash" in model_name or "gemini-1.5-flash" in model_name:
            clean_model = "gemini-1.5-flash"

        prompt = MeetingActaSummarizer.ACTA_PROMPT_TEMPLATE.format(
            title=title,
            date="Hoy",
            duration=duration,
            participants=participants,
            transcript=transcript.strip()  # Gemini soporta millones de tokens, texto completo sin recortes
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
                "maxOutputTokens": 4096
            }
        }

        try:
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=(10, 120))
            if r.status_code != 200:
                err_text = r.text
                try:
                    err_json = r.json()
                    err_text = err_json.get('error', {}).get('message', r.text)
                except Exception:
                    pass
                yield {"token": f"❌ Error de Gemini API ({r.status_code}): {err_text}", "done": True}
                return

            has_tokens = False
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if line_str.startswith('data: '):
                        raw_json = line_str[6:].strip()
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
                yield {"token": "⚠️ No se recibieron datos de Gemini API.", "done": True}
            else:
                yield {"token": "", "done": True}

        except Exception as e:
            yield {"token": f"❌ Error de conexión con Gemini: {str(e)}", "done": True}

    # =========================================================================
    # OLLAMA LOCAL ENGINE
    # =========================================================================
    @staticmethod
    def stream_summary_ollama(transcript: str, title: str = "Reunión", duration: str = "N/A",
                             participants: str = "Hablantes detectados",
                             model: str = "llama3:latest", host: str = "http://localhost:11434"):
        """Genera el Acta Oficial con Ollama transmitiendo tokens con timeout amplio y soporte de modelos locales."""
        clean_model = model.replace("Ollama: ", "").strip()
        optimized_text = MeetingActaSummarizer._optimize_context_for_ollama(transcript)

        if not optimized_text:
            yield {"token": "⚠️ La transcripción está vacía.", "done": True}
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
            # Timeout generoso (45s para carga en VRAM, 180s para streaming)
            r = requests.post(
                f"{host}/api/generate",
                json={
                    "model": clean_model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_ctx": 16384,
                        "num_predict": 2500
                    }
                },
                stream=True,
                timeout=(45, 180)
            )

            if r.status_code == 200:
                for line in r.iter_lines():
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

        # Si falló Ollama, notificar y ofrecer fallback explícito
        if not has_streamed_any:
            fallback = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration, participants=participants)
            if error_msg:
                yield {"token": f"> ⚠️ *Aviso del Sistema: {error_msg}. Mostrando síntesis de respaldo.*\\n\\n" + fallback, "done": True}
            else:
                yield {"token": fallback, "done": True}

    @staticmethod
    def generate_heuristic_summary(transcript: str, title: str = "Reunión", duration: str = "N/A", participants: str = "Hablantes detectados"):
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

        acta_text = f"""# 📜 ACTA OFICIAL DE SESIÓN (Heurístico Offline): {title}
**Fecha:** Hoy  |  **Duración:** {duration}  |  **Participantes:** {participants}

---

### 📌 1. SÍNTESIS EJECUTIVA
{overview_text}

---

### 🎯 2. ACUERDOS Y DECISIONES CLAVE
"""
        if decisions:
            for d in decisions[:6]:
                acta_text += f"- {d}\n"
        else:
            acta_text += "- Se revisaron los avances principales y la continuidad de las actividades planteadas.\n"
            acta_text += "- Se acordó mantener seguimiento continuo sobre los entregables del proyecto.\n"

        acta_text += "\n### ✅ 3. COMPROMISOS Y TAREAS ASIGNADAS (ACTION ITEMS)\n"
        if actions:
            for a in actions[:8]:
                acta_text += f"- [ ] {a}\n"
        else:
            acta_text += "- [ ] **Equipo**: Revisar puntos presentados en la sesión y coordinar próximos entregables.\n"
            acta_text += "- [ ] **Coordinación**: Confirmar calendario de entregas y requerimientos pendientes.\n"

        acta_text += """
---

### 💡 4. PUNTOS CRÍTICOS Y TEMAS PENDIENTES
- Confirmar agenda y fecha para la próxima sesión de revisión.
- Validar requerimientos técnicos y documentación correspondiente.
"""
        return acta_text
