import re

class SpeakerDiarizer:
    """Módulo de agrupación fluida de hablantes e inferencia de turnos de diálogo."""
    
    # Patrones de nombres e introducción en español
    NAME_PATTERNS = [
        r'(?:mi nombre es|me llamo|soy|les habla|habla)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)',
        r'(?:gracias|hola|bienvenido|adelante|escuchamos a)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)',
        r'(?:la palabra a|le doy la palabra a)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)',
        r'(?:como decía|como dijo)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)'
    ]
    
    @staticmethod
    def perform_diarization(segments):
        """
        Asigna etiquetas de hablante y agrupa en turnos de habla fluidos y naturales.
        """
        if not segments:
            return []

        current_speaker_id = 1
        last_end = 0.0
        
        raw_tagged = []

        for seg in segments:
            start = seg.get('start', 0.0)
            end = seg.get('end', 0.0)
            text = seg.get('text', '').strip()
            if not text:
                continue
            
            # Solo cambiar de hablante si hay un silencio largo y marcado (> 4.5s)
            pause_duration = start - last_end
            if pause_duration > 4.5 and len(raw_tagged) > 0:
                current_speaker_id = 2 if current_speaker_id == 1 else 1

            speaker_tag = f"Hablante {current_speaker_id}"
            tentative_name = SpeakerDiarizer.detect_tentative_name(text)
            
            raw_tagged.append({
                'start': start,
                'end': end,
                'text': text,
                'speaker': speaker_tag,
                'tentative_name': tentative_name,
                'is_tentative': bool(tentative_name)
            })
            
            last_end = end

        # Consolidar en turnos fluidos (merge contiguous segments of same speaker)
        return SpeakerDiarizer.group_segments_by_speaker(raw_tagged)

    @staticmethod
    def group_segments_by_speaker(segments, max_gap=8.0):
        """
        Agrupa segmentos consecutivos del mismo hablante en un solo bloque fluido y continuo.
        """
        if not segments:
            return []
        
        grouped = []
        current_turn = None
        
        for seg in segments:
            spk = seg.get('speaker', 'Hablante 1')
            text = seg.get('text', '').strip()
            start = seg.get('start', 0.0)
            end = seg.get('end', 0.0)
            
            if not text:
                continue
                
            if current_turn is None:
                current_turn = {
                    'speaker': spk,
                    'start': start,
                    'end': end,
                    'texts': [text],
                    'tentative_name': seg.get('tentative_name'),
                    'is_tentative': seg.get('is_tentative', False)
                }
            elif current_turn['speaker'] == spk and (start - current_turn['end'] <= max_gap):
                current_turn['texts'].append(text)
                current_turn['end'] = end
                if not current_turn.get('tentative_name') and seg.get('tentative_name'):
                    current_turn['tentative_name'] = seg.get('tentative_name')
                    current_turn['is_tentative'] = True
            else:
                # Guardar turno consolidado
                current_turn['text'] = " ".join(current_turn['texts'])
                del current_turn['texts']
                grouped.append(current_turn)
                
                # Iniciar nuevo turno
                current_turn = {
                    'speaker': spk,
                    'start': start,
                    'end': end,
                    'texts': [text],
                    'tentative_name': seg.get('tentative_name'),
                    'is_tentative': seg.get('is_tentative', False)
                }
                
        if current_turn:
            current_turn['text'] = " ".join(current_turn['texts'])
            if 'texts' in current_turn:
                del current_turn['texts']
            grouped.append(current_turn)
            
        return grouped

    @staticmethod
    def detect_tentative_name(text):
        """Busca patrones de nombres propios o frases de presentación en el texto."""
        if not text:
            return None
        
        for pattern in SpeakerDiarizer.NAME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).capitalize()
                ignore = {'Gracias', 'Hola', 'Todos', 'Que', 'Para', 'Como', 'Bueno', 'Entonces', 'Digamos', 'Pues'}
                if candidate not in ignore and len(candidate) > 2:
                    return candidate
        return None

    @staticmethod
    def format_transcript_with_speakers(grouped_segments):
        """Formatea la transcripción estructurada en turnos de diálogo fluidos."""
        blocks = []
        for turn in grouped_segments:
            spk = turn.get('speaker', 'Hablante 1')
            tentative = turn.get('tentative_name')
            
            if turn.get('is_tentative') and tentative and '(' not in spk:
                spk_display = f"{spk} (¿{tentative}?)"
            else:
                spk_display = spk
                
            start_str = SpeakerDiarizer.format_timestamp(turn.get('start', 0.0))
            text = turn.get('text', '').strip()
            blocks.append(f"⏱️ [{start_str}] {spk_display}:\n{text}")
            
        return "\n\n".join(blocks)

    @staticmethod
    def format_timestamp(seconds):
        """Formatea segundos a HH:MM:SS."""
        secs = int(seconds)
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
