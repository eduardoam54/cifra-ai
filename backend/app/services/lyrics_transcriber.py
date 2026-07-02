"""
Transcrição de letra (backlog 9.1, seção 9.1 do plano) via faster-whisper,
rodando sobre o stem de vocais isolado pelo Demucs.

Opt-in via LYRICS_ENABLED (padrão desligado) — é um modelo pesado a mais
rodando na CPU, e a precisão cai um pouco mesmo com o vocal isolado por
causa de vazamento de instrumentação no stem.

Risco de copyright maior que acordes/BPM/tom (ver plano seção 7.1/9.1: letra
é conteúdo protegido, diferente de acorde/BPM/tom que são tratados como
fato) — por isso o resultado NUNCA é persistido no cache Supabase
(app/services/cache.py monta o payload de save_analysis manualmente e não
inclui `lyrics`; isso é intencional, não esquecimento).
"""

import logging
from functools import lru_cache

from app.config import get_settings
from app.models import LyricLine

logger = logging.getLogger(__name__)


@lru_cache
def _get_model():
    from faster_whisper import WhisperModel

    settings = get_settings()
    logger.info("Carregando modelo faster-whisper (%s)...", settings.lyrics_model_size)
    return WhisperModel(settings.lyrics_model_size, device="cpu", compute_type="int8")


def transcribe_lyrics(vocals_path: str) -> list[LyricLine]:
    """Transcreve `vocals_path` em linhas com timestamp. Retorna [] se
    LYRICS_ENABLED=false (comportamento padrão — feature é opt-in)."""
    settings = get_settings()
    if not settings.lyrics_enabled:
        return []

    model = _get_model()
    segments, _info = model.transcribe(vocals_path, word_timestamps=False)

    lines = [
        LyricLine(start=round(seg.start, 2), end=round(seg.end, 2), text=seg.text.strip())
        for seg in segments
        if seg.text.strip()
    ]

    logger.info("Transcrição de letra: %d linhas", len(lines))
    return lines
