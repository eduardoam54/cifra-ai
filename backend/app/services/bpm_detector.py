"""
Detecção de BPM via estimador global de tempo do librosa.

Usa o mix completo (ou qualquer stem) para estimar o andamento.
Retorna float com BPM arredondado para 1 casa decimal.
"""

import logging
import numpy as np
import librosa

logger = logging.getLogger(__name__)


def detect_bpm(audio_path: str) -> float:
    """Estima BPM a partir de `audio_path`.

    Usa `librosa.feature.tempo` (autocorrelação do tempograma) em vez de
    `librosa.beat.beat_track`: em áudio com pouca percussão/onset fraco
    (ex.: trechos curtos ou predominantemente melódicos), beat_track não
    encontra uma sequência de batidas e retorna 0.0 BPM; feature.tempo dá
    uma estimativa de qualquer forma, com a mesma precisão em áudio
    percussivo normal (validado com um click track sintético).
    """
    y, sr = librosa.load(audio_path, mono=True)
    tempo = librosa.feature.tempo(y=y, sr=sr)

    # librosa >= 0.10 retorna np.ndarray de 1 elemento
    bpm = float(np.atleast_1d(tempo)[0])
    bpm = round(bpm, 1)

    logger.info("BPM detectado: %.1f", bpm)
    return bpm
