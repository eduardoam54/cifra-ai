"""
Detecção de tonalidade por correlação de Krumhansl-Schmuckler.

Computa o chroma do áudio e correlaciona com os perfis de maior e menor
para todas as 12 tônicas. A tonalidade com maior correlação vence.
"""

import logging
import numpy as np
import librosa

logger = logging.getLogger(__name__)

# Perfis KS (Krumhansl-Schmuckler, 1990) — padrão da literatura
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]


def _ks_correlation(chroma_mean: np.ndarray, profile: np.ndarray) -> np.ndarray:
    """Correlação de Pearson entre o chroma médio e o perfil para cada tônica."""
    scores = np.zeros(12)
    for tonic in range(12):
        rotated = np.roll(profile, tonic)
        scores[tonic] = np.corrcoef(chroma_mean, rotated)[0, 1]
    return scores


def detect_key(audio_path: str) -> str:
    """
    Retorna a tonalidade em formato legível, ex.: 'A maior' ou 'D# menor'.
    """
    y, sr = librosa.load(audio_path, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)  # shape (12,)

    major_scores = _ks_correlation(chroma_mean, _MAJOR)
    minor_scores = _ks_correlation(chroma_mean, _MINOR)

    best_major_idx = int(np.argmax(major_scores))
    best_minor_idx = int(np.argmax(minor_scores))

    if major_scores[best_major_idx] >= minor_scores[best_minor_idx]:
        key = f"{_NOTE_NAMES[best_major_idx]} maior"
    else:
        key = f"{_NOTE_NAMES[best_minor_idx]} menor"

    logger.info("Tonalidade detectada: %s", key)
    return key
