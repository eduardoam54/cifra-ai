"""
Reconhecimento de acordes — interface plugável.

Backend selecionado via settings.chord_backend:
  "chroma"      → ChromaChordRecognizer      (fallback, usa stems separados pelo Demucs)
  "chroma_fast" → ChromaFastChordRecognizer  (backlog 9.2 opção B: pula o Demucs, mais
                                               rápido, perde precisão em slash chords)
  "btc"         → BTCChordRecognizer         (requer peso pré-treinado em chord_model_path)

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
    #: Se False, o router pula a separação Demucs e passa {"mix": audio_path}
    #: em vez dos stems reais (ver ChromaFastChordRecognizer / backlog 9.2).
    NEEDS_SEPARATION: bool = True

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

# Qualidades reconhecidas: sufixo do símbolo → intervalos em semitons a partir
# da fundamental. Fase 4 (plano, seção 4.1): antes só tríades maior/menor —
# isso ainda não é um modelo ACR de verdade (exigiria peso pré-treinado tipo
# BTC/Chordformer, ver BTCChordRecognizer), mas amplia o vocabulário além da
# tríade mais próxima para as qualidades mais comuns em cifras.
_QUALITIES: dict[str, tuple[int, ...]] = {
    "": (0, 4, 7),          # maior
    "m": (0, 3, 7),         # menor
    "7": (0, 4, 7, 10),     # dominante
    "maj7": (0, 4, 7, 11),  # maior com sétima maior
    "m7": (0, 3, 7, 10),    # menor com sétima menor
    "m7b5": (0, 3, 6, 10),  # meio-diminuto
    "dim": (0, 3, 6),       # diminuto
    "aug": (0, 4, 8),       # aumentado
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
}


def _build_templates() -> tuple[np.ndarray, list[str]]:
    """Gera os templates de chroma (um por acorde) e os nomes correspondentes.

    shape: (12 tônicas × len(_QUALITIES), 12 pitch classes)
    """
    templates = []
    names = []
    for suffix, intervals in _QUALITIES.items():
        for root in range(12):
            template = np.zeros(12)
            template[[(root + i) % 12 for i in intervals]] = 1.0
            templates.append(template)
            names.append(f"{_PC_TO_NOTE[root]}{suffix}")
    return np.array(templates), names


_TEMPLATES, _CHORD_NAMES = _build_templates()
_TEMPLATE_NORMS = np.linalg.norm(_TEMPLATES, axis=1)


def _events_from_chroma(chroma: np.ndarray, hop_s: float) -> list[ChordEvent]:
    """Template matching frame a frame + agrupamento de frames consecutivos
    com o mesmo acorde. Compartilhado entre os backends baseados em chroma
    (com e sem separação de stems — ver ChromaFastChordRecognizer)."""
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

        start = i * hop_s
        end = (i + 1) * hop_s

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

    return events


class ChromaChordRecognizer(BaseChordRecognizer):
    """
    Reconhecimento por template matching sobre chroma harmônico.

    Funde o stem de baixo (fundamental) com o stem "other" (qualidade)
    para melhorar a identificação — mesma lógica do pipeline completo,
    só sem modelo de ML.

    Precisão: boa para tríades e as qualidades em _QUALITIES; combinações
    fora desse vocabulário (tensões, acordes alterados) caem na mais próxima.
    """

    HOP_S: float = 0.5   # janela de análise em segundos
    NEEDS_SEPARATION = True

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

        events = _events_from_chroma(chroma, self.HOP_S)
        logger.info("ChromaRecognizer: %d eventos de acorde detectados", len(events))
        return events


# ---------------------------------------------------------------------------
# Backend 2 — Chroma sem separação (backlog 9.2, opção B: "modo rápido")
# ---------------------------------------------------------------------------

class ChromaFastChordRecognizer(BaseChordRecognizer):
    """
    Reconhece acordes direto na mixagem completa via chroma, sem separar
    stems com o Demucs — pula de longe a parte mais cara do pipeline.

    Trade-off (ver seção 4.1/9.2 do plano): sem o stem de baixo isolado pra
    reforçar a fundamental, perde precisão em inversões/slash chords (ex.:
    C/A pode sair como Am), mas é muito mais rápido pra primeira análise.
    """

    HOP_S: float = 0.5
    NEEDS_SEPARATION = False

    def recognize(self, stems: dict[str, str]) -> list[ChordEvent]:
        y, sr = librosa.load(stems["mix"], mono=True)
        hop = int(sr * self.HOP_S)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)

        events = _events_from_chroma(chroma, self.HOP_S)
        logger.info("ChromaFastRecognizer: %d eventos de acorde detectados (sem separação)",
                    len(events))
        return events


# ---------------------------------------------------------------------------
# Backend 3 — BTC (placeholder — ativa quando o peso estiver disponível)
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
    "chroma_fast": ChromaFastChordRecognizer,
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
