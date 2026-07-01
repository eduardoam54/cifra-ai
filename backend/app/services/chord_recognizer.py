"""
Reconhecimento de acordes — interface plugável.

Backend selecionado via settings.chord_backend:
  "chroma"  → ChromaChordRecognizer  (fallback, sem modelo externo, usa só librosa)
  "btc"     → BTCChordRecognizer     (requer peso pré-treinado em settings.chord_model_path)

Para adicionar um novo backend:
  1. Crie uma classe que herde de BaseChordRecognizer.
  2. Implemente recognize(stems) → list[ChordEvent].
  3. Registre-a no dict BACKENDS.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import librosa

from app.models import ChordEvent
from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface base
# ---------------------------------------------------------------------------

class BaseChordRecognizer(ABC):
    @abstractmethod
    def recognize(self, stems: dict[str, str]) -> list[ChordEvent]:
        """
        Recebe os caminhos dos stems separados pelo Demucs e devolve
        a timeline de acordes.

        stems: {"bass": "/path/bass.wav", "vocals": ..., "other": ...}
               "drums" pode estar presente mas deve ser ignorado.
        """


# ---------------------------------------------------------------------------
# Backend 1 — Chroma simples (librosa) — funciona sem modelo externo
# ---------------------------------------------------------------------------

# Mapeamento de pitch class → nota
_PC_TO_NOTE = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]

# Templates de acorde: tríades maiores e menores para cada tônica
# shape (24, 12) — 12 maiores + 12 menores
def _build_templates() -> np.ndarray:
    templates = []
    for root in range(12):
        # maior: root, terça maior (+4), quinta (+7)
        major = np.zeros(12)
        major[[root, (root + 4) % 12, (root + 7) % 12]] = 1.0
        templates.append(major)
    for root in range(12):
        # menor: root, terça menor (+3), quinta (+7)
        minor = np.zeros(12)
        minor[[root, (root + 3) % 12, (root + 7) % 12]] = 1.0
        templates.append(minor)
    return np.array(templates)  # (24, 12)


_TEMPLATES = _build_templates()
_TEMPLATE_NORMS = np.linalg.norm(_TEMPLATES, axis=1)

_CHORD_NAMES = (
    [f"{n}" for n in _PC_TO_NOTE] +          # maiores
    [f"{n}m" for n in _PC_TO_NOTE]           # menores
)


class ChromaChordRecognizer(BaseChordRecognizer):
    """
    Reconhecimento por template matching sobre chroma harmônico.

    Funde o stem de baixo (fundamental) com o stem "other" (qualidade)
    para melhorar a identificação — mesma lógica do pipeline completo,
    só sem modelo de ML.

    Precisão: boa para tríades comuns; acordes extendidos/alterados
    serão simplificados para a tríade mais próxima.
    """

    HOP_S: float = 0.5   # janela de análise em segundos

    def recognize(self, stems: dict[str, str]) -> list[ChordEvent]:
        # Funde baixo + harmonia (voz + outros)
        y_bass, sr = librosa.load(stems["bass"], mono=True)
        y_harm, _ = librosa.load(stems["other"], sr=sr, mono=True)

        # Garante mesmo comprimento
        min_len = min(len(y_bass), len(y_harm))
        y_bass, y_harm = y_bass[:min_len], y_harm[:min_len]

        # Chroma: baixo reforça a fundamental, harmônico dá qualidade
        hop = int(sr * self.HOP_S)
        chroma_bass = librosa.feature.chroma_cqt(y=y_bass, sr=sr, hop_length=hop)
        chroma_harm = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop)
        chroma = 0.6 * chroma_bass + 0.4 * chroma_harm  # fusão ponderada

        n_frames = chroma.shape[1]
        events: list[ChordEvent] = []

        for i in range(n_frames):
            frame = chroma[:, i]
            # Correlação com cada template (cosseno — normaliza por ambas as normas)
            scores = _TEMPLATES @ frame
            best = int(np.argmax(scores))
            chord = _CHORD_NAMES[best]
            cosine = scores[best] / (np.linalg.norm(frame) * _TEMPLATE_NORMS[best] + 1e-8)
            confidence = float(np.clip(cosine, 0.0, 1.0))

            start = i * self.HOP_S
            end = (i + 1) * self.HOP_S

            # Agrupa frames consecutivos com o mesmo acorde
            if events and events[-1].chord == chord:
                events[-1] = ChordEvent(
                    start=events[-1].start,
                    end=end,
                    chord=chord,
                    confidence=round(((events[-1].confidence or 0) + confidence) / 2, 3),
                )
            else:
                events.append(ChordEvent(
                    start=round(start, 3),
                    end=round(end, 3),
                    chord=chord,
                    confidence=round(confidence, 3),
                ))

        logger.info("ChromaRecognizer: %d eventos de acorde detectados", len(events))
        return events


# ---------------------------------------------------------------------------
# Backend 2 — BTC (placeholder — ativa quando o peso estiver disponível)
# ---------------------------------------------------------------------------

class BTCChordRecognizer(BaseChordRecognizer):
    """
    Wrapper para o modelo BTC (Bidirectional Transformer for Chord).

    Requer:
      - Peso ONNX ou PyTorch em settings.chord_model_path
      - Biblioteca btc_model (instalar à parte)

    Enquanto o peso não estiver disponível, levanta NotImplementedError
    em vez de falhar silenciosamente.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.chord_model_path:
            raise NotImplementedError(
                "BTC backend requer CHORD_MODEL_PATH configurado no .env"
            )
        # TODO: carregar peso ONNX/PyTorch aqui
        # self.model = load_btc_model(settings.chord_model_path)
        raise NotImplementedError("BTC backend ainda não implementado — use chord_backend=chroma")

    def recognize(self, stems: dict[str, str]) -> list[ChordEvent]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

BACKENDS: dict[str, type[BaseChordRecognizer]] = {
    "chroma": ChromaChordRecognizer,
    "btc": BTCChordRecognizer,
}


def get_chord_recognizer() -> BaseChordRecognizer:
    settings = get_settings()
    backend_cls = BACKENDS.get(settings.chord_backend)
    if backend_cls is None:
        raise ValueError(
            f"chord_backend desconhecido: '{settings.chord_backend}'. "
            f"Opções: {list(BACKENDS)}"
        )
    return backend_cls()
