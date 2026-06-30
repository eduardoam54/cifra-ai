"""
Detecção de BPM via librosa beat tracking.

Usa o mix completo (ou qualquer stem) para estimar o andamento.
Retorna float com BPM arredondado para 1 casa decimal.
"""

import logging
import numpy as np
import librosa

logger = logging.getLogger(__name__)


def detect_bpm(audio_path: str) -> float:
    """Estima BPM a partir de `audio_path`."""
    y, sr = librosa.load(audio_path, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    # librosa >= 0.10 retorna np.ndarray de 1 elemento
    bpm = float(np.atleast_1d(tempo)[0])
    bpm = round(bpm, 1)

    logger.info("BPM detectado: %.1f", bpm)
    return bpm
