import os
import re
import json
import requests
import threading

class MeetingActaSummarizer:
    """Generador del Acta Oficial de Sesión e Insights con soporte nativo para Ollama e IA Local."""

    ACTA_PROMPT_TEMPLATE = """Eres un asistente ejecutivo de alto nivel especializado en redactar el Acta Oficial de Sesión e Insights clave de reuniones de trabajo.
A partir de la siguiente transcripción, redacta un acta profesional, estructurada y limpia en español.

DEBES SEGUIR EXACTAMENTE ESTA ESTRUCTURA DE ACTA OFICIAL:

📜 ACTA OFICIAL DE SESIÓN: {title}
======================================================================
Fecha: {date}  |  Duración: {duration}  |  Participantes: {participants}
----------------------------------------------------------------------

📌 SÍNTESIS EJECUTIVA
[Sintetiza en 2 a 3 párrafos el objetivo central, el contexto y los temas clave discutidos en la sesión]

🎯 ACUERDOS Y DECISIONES CLAVE
• [Decisión o acuerdo alcanzado 1]
• [Decisión o acuerdo alcanzado 2]
• [Decisión o acuerdo alcanzado 3]

✅ COMPROMISOS Y TAREAS ASIGNADAS (ACTION ITEMS)
[ ] [Encargado o Hablante]: [Tarea específica acordada y fecha tentativa si se mencionó]
[ ] [Encargado o Hablante]: [Tarea específica acordada y fecha tentativa si se mencionó]

💡 PUNTOS DE DEBATE Y TEMAS PENDIENTES
• [Asunto o tema que requiere seguimiento en la siguiente sesión]
• [Dudas o requerimientos pendientes de resolver]
======================================================================

TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{transcript}
"""

    @staticmethod
    def _clean_transcript_text(transcript: str) -> str:
        """Elimina marcas de tiempo y etiquetas [Hablante N] para síntesis limpia."""
        cleaned = re.sub(r'⏱\s*\d+:\d+(?::\d+)?\s*\[.*?\]:\s*', '', transcript)
        cleaned = re.sub(r'\[Hablante\s*\d+.*?\]:\s*', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def _optimize_context_for_llm(transcript: str, max_chars: int = 7500) -> str:
        """Extrae un extracto de alta densidad semántica con inicio, acuerdos/acciones y cierre."""
        clean = MeetingActaSummarizer._clean_transcript_text(transcript)
        if len(clean) <= max_chars:
            return clean

        lines = [l.strip() for l in clean.split('\n') if l.strip()]
        if not lines:
            return clean[:max_chars]

        # 1. Apertura e introducción (~ 2000 caracteres)
        head = []
        head_len = 0
        for l in lines[:15]:
            head.append(l)
            head_len += len(l)
            if head_len >= 2000:
                break

        # 2. Extractos intermedios con palabras de acción, compromisos y decisiones (~ 3500 caracteres)
        action_keywords = ['acuerd', 'comprom', 'hacer', 'revis', 'enviar', 'pago', 'entrega', 'mañana', 'semana', 'tarea', 'responsable', 'decidi', 'conclusi', 'aprob', 'confirm', 'defin', 'objetivo', 'desembol', 'proyecto', 'presupuesto']
        middle = []
        middle_len = 0
        mid_lines = lines[len(head):-15] if len(lines) > 30 else []
        for l in mid_lines:
            if any(k in l.lower() for k in action_keywords):
                middle.append(l)
                middle_len += len(l)
                if middle_len >= 3500:
                    break

        # 3. Cierre y conclusiones (~ 2000 caracteres)
        tail = []
        tail_len = 0
        for l in reversed(lines[-15:]):
            tail.insert(0, l)
            tail_len += len(l)
            if tail_len >= 2000:
                break

        combined_parts = []
        if head:
            combined_parts.append("\n".join(head))
        if middle:
            combined_parts.append("\n--- [DISCUSIÓN DE ACUERDOS Y COMPROMISOS] ---\n" + "\n".join(middle))
        if tail:
            combined_parts.append("\n--- [CONCLUSIONES Y PRÓXIMOS PASOS] ---\n" + "\n".join(tail))

        result = "\n\n".join(combined_parts)
        return result[:max_chars]

    @staticmethod
    def get_ollama_models(host="http://localhost:11434"):
        """Detecta dinámicamente el estado de Ollama y los modelos instalados."""
        available = []
        try:
            r = requests.get(f"{host}/api/tags", timeout=1.5)
            if r.status_code == 200:
                models = r.json().get('models', [])
                if models:
                    for m in models:
                        available.append(f"Ollama: {m['name']}")
                else:
                    available.append("⚠️ Ollama activo (sin modelos)")
        except Exception:
            available.append("⚠️ Ollama Desconectado")

        available.append("📝 Resumen Heurístico Offline")
        return available

    @staticmethod
    def generate_summary_ollama(transcript, title="Reunión", duration="N/A", participants="Hablantes detectados", model="qwen2.5:latest", host="http://localhost:11434"):
        """Genera el Acta Oficial usando Ollama con control estricto de errores y fallback automático."""
        clean_model = model.replace("Ollama: ", "").strip()
        optimized_text = MeetingActaSummarizer._optimize_context_for_llm(transcript)
        
        if not optimized_text:
            raise ValueError("La transcripción está vacía.")

        prompt = MeetingActaSummarizer.ACTA_PROMPT_TEMPLATE.format(
            title=title,
            date="Hoy",
            duration=duration,
            participants=participants,
            transcript=optimized_text
        )
        
        try:
            r = requests.post(
                f"{host}/api/generate",
                json={
                    "model": clean_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                        "num_predict": 1200,
                        "num_gpu": 99
                    }
                },
                timeout=45
            )
            if r.status_code == 200:
                response_text = r.json().get('response', '').strip()
                if response_text:
                    return response_text
        except Exception as e:
            pass

        # Fallback resiliente al motor heurístico
        return MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration, participants=participants)

    @staticmethod
    def stream_summary_ollama(transcript, title="Reunión", duration="N/A", participants="Hablantes detectados", model="qwen2.5:latest", host="http://localhost:11434"):
        """Genera el Acta Oficial transmitiendo tokens en tiempo real con fallback resiliente automático."""
        clean_model = model.replace("Ollama: ", "").strip()
        optimized_text = MeetingActaSummarizer._optimize_context_for_llm(transcript)
        
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
        try:
            r = requests.post(
                f"{host}/api/generate",
                json={
                    "model": clean_model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                        "num_predict": 1200,
                        "num_gpu": 99
                    }
                },
                stream=True,
                timeout=(5, 60)
            )
            if r.status_code == 200:
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            token = chunk.get('response', '')
                            done = chunk.get('done', False)
                            if token:
                                has_streamed_any = True
                                yield {"token": token, "done": done}
                            if done:
                                return
                        except Exception:
                            pass
        except Exception as e:
            pass

        # Si Ollama falló o no emitió tokens, fallback automático al resumen offline sin bloquear la UI
        if not has_streamed_any:
            fallback = MeetingActaSummarizer.generate_heuristic_summary(transcript, title=title, duration=duration, participants=participants)
            yield {"token": fallback, "done": True}

    @staticmethod
    def generate_heuristic_summary(transcript, title="Reunión", duration="N/A", participants="Hablantes detectados"):
        """Generador heurístico offline estructurado sin dependencias externas."""
        clean_text = MeetingActaSummarizer._clean_transcript_text(transcript)
        lines = [line.strip() for line in clean_text.split('\n') if line.strip() and len(line.strip()) > 15]
        
        action_keywords = ['acuerd', 'compromet', 'hacer', 'revisar', 'enviar', 'pago', 'entrega', 'mañana', 'semana', 'lanzar', 'tarea', 'responsable']
        decision_keywords = ['quedam', 'decidi', 'conclusi', 'aprob', 'confirm', 'defin', 'presenta', 'acordamos', 'objetivo']
        
        actions = []
        decisions = []
        
        for line in lines:
            line_lower = line.lower()
            if any(k in line_lower for k in action_keywords) and len(line) < 220:
                actions.append(line)
            elif any(k in line_lower for k in decision_keywords) and len(line) < 220:
                decisions.append(line)

        # Generar síntesis inicial de los primeros párrafos
        overview_text = ""
        if lines:
            first_chunks = lines[:6]
            overview_text = " ".join(first_chunks)
            if len(overview_text) > 400:
                overview_text = overview_text[:400] + "..."
        else:
            overview_text = "Sesión de trabajo y seguimiento de actividades generales del proyecto."

        acta_text = f"""📜 ACTA OFICIAL DE SESIÓN (Heurístico Offline): {title}
======================================================================
Fecha: Hoy  |  Duración: {duration}  |  Participantes: {participants}
----------------------------------------------------------------------

📌 SÍNTESIS EJECUTIVA
{overview_text}

----------------------------------------------------------------------
🎯 ACUERDOS Y DECISIONES CLAVE
"""
        if decisions:
            for d in decisions[:6]:
                acta_text += f"• {d}\n"
        else:
            acta_text += "• Se revisaron los avances principales y la continuidad de las actividades planteadas.\n"
            acta_text += "• Se acordó mantener seguimiento continuo sobre los entregables del proyecto.\n"

        acta_text += "\n✅ COMPROMISOS Y TAREAS ASIGNADAS (ACTION ITEMS)\n"
        if actions:
            for a in actions[:8]:
                acta_text += f"[ ] {a}\n"
        else:
            acta_text += "[ ] Equipo: Revisar puntos presentados en la sesión y coordinar próximos entregables.\n"
            acta_text += "[ ] Coordinación: Confirmar calendario de entregas y requerimientos pendientes.\n"

        acta_text += """
----------------------------------------------------------------------
💡 PUNTOS DE DEBATE Y TEMAS PENDIENTES
• Confirmar agenda y fecha para la próxima sesión de revisión.
• Validar requerimientos y firmas de documentación correspondientes.
======================================================================
"""
        return acta_text
