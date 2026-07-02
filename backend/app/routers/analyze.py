"""
Router /analyze — endpoint principal da Fase 0.

POST /analyze
  Body: multipart/form-data
    audio_file: arquivo de áudio (wav, mp3, flac, ogg, m4a…)
    video_id:   (opcional) ID do YouTube ou outro identificador de cache

Resposta: AnalysisResponse (JSON)
"""

import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.models import AnalysisResponse
from app.services.bpm_detector import detect_bpm
from app.services.cache import get_cached_analysis, save_analysis
from app.services.chord_recognizer import get_chord_recognizer
from app.services.key_detector import detect_key
from app.services.lyrics_transcriber import transcribe_lyrics
from app.services.separator import separate_stems

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])

_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".webm"}


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_audio(
    audio_file: UploadFile = File(..., description="Arquivo de áudio para análise"),
    video_id: str | None = Form(None, description="ID do YouTube ou hash — chave de cache"),
) -> AnalysisResponse:
    """
    Recebe um arquivo de áudio e devolve a timeline de acordes, BPM e tonalidade.

    Pipeline:
      1. Consulta o cache (Supabase) por `video_id` — se houver hit, retorna direto
      2. Salva o arquivo em diretório temporário
      3. Valida duração máxima
      4. Separa stems com Demucs (pulado se chord_backend=chroma_fast — backlog 9.2)
      5. Detecta BPM, tonalidade e acordes em paralelo (stem-level)
      6. Transcreve letra se LYRICS_ENABLED=true (opt-in, nunca cacheado)
      7. Salva no cache, devolve AnalysisResponse e limpa arquivos temporários
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())

    cached = get_cached_analysis(video_id)
    if cached is not None:
        logger.info("[%s] Cache hit para video_id=%s", request_id, video_id)
        return cached

    # Valida extensão
    suffix = Path(audio_file.filename or "audio").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Formato não suportado: '{suffix}'. Aceitos: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    work_dir = tempfile.mkdtemp(prefix=f"cifras_{request_id}_")
    try:
        # Salva o upload em disco
        audio_path = os.path.join(work_dir, f"input{suffix}")
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)

        logger.info("[%s] Arquivo salvo: %s (%.1f KB)",
                    request_id, audio_path, os.path.getsize(audio_path) / 1024)

        t_start = time.perf_counter()

        recognizer = get_chord_recognizer()
        if recognizer.NEEDS_SEPARATION:
            stems_dir = os.path.join(work_dir, "stems")
            os.makedirs(stems_dir, exist_ok=True)
            stems = separate_stems(audio_path, stems_dir)
        else:
            # Modo rápido (backlog 9.2): pula o Demucs, reconhece direto na mixagem.
            stems = {"mix": audio_path}

        # Detecção paralela: BPM usa o áudio original; chroma usa stems
        bpm = detect_bpm(audio_path)
        key = detect_key(audio_path)

        chords_timeline = recognizer.recognize(stems)

        # Opt-in (LYRICS_ENABLED) e nunca persistido no cache — ver 7.1/9.1 do plano.
        # Sem separação (modo rápido), não há stem de vocais isolado — usa a mixagem.
        lyrics = transcribe_lyrics(stems.get("vocals", audio_path))

        processing_time = round(time.perf_counter() - t_start, 2)
        logger.info("[%s] Concluído em %.2fs — %d acordes detectados",
                    request_id, processing_time, len(chords_timeline))

        result = AnalysisResponse(
            request_id=request_id,
            video_id=video_id,
            bpm=bpm,
            key=key,
            chords_timeline=chords_timeline,
            model_version=settings.model_version,
            processing_time_s=processing_time,
            lyrics=lyrics,
        )
        save_analysis(result)
        return result

    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception as exc:
        logger.exception("[%s] Erro durante análise", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc}",
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
