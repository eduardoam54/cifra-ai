"""
Testes de app/services/lyrics_transcriber.py — o modelo faster-whisper é
substituído por um fake via monkeypatch, sem baixar pesos nem depender de
áudio real. Cobrem principalmente o opt-in (LYRICS_ENABLED) e o formato
da saída, que é o que importa pro contrato com o router.
"""

from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.services import lyrics_transcriber


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    lyrics_transcriber._get_model.cache_clear()
    yield
    get_settings.cache_clear()
    lyrics_transcriber._get_model.cache_clear()


def test_desabilitado_por_padrao_nao_chama_modelo(monkeypatch):
    monkeypatch.setenv("LYRICS_ENABLED", "false")
    get_settings.cache_clear()

    def _boom():
        raise AssertionError("não deveria carregar o modelo com LYRICS_ENABLED=false")

    monkeypatch.setattr(lyrics_transcriber, "_get_model", _boom)
    assert lyrics_transcriber.transcribe_lyrics("qualquer.wav") == []


def test_habilitado_transcreve_e_formata_linhas(monkeypatch):
    monkeypatch.setenv("LYRICS_ENABLED", "true")
    get_settings.cache_clear()

    fake_segments = [
        SimpleNamespace(start=0.001, end=1.999, text="  primeira linha  "),
        SimpleNamespace(start=2.0, end=3.5, text="segunda linha"),
        SimpleNamespace(start=3.5, end=4.0, text="   "),  # linha vazia é descartada
    ]

    class FakeModel:
        def transcribe(self, path, word_timestamps=False):
            assert path == "vocals.wav"
            return fake_segments, {"language": "pt"}

    monkeypatch.setattr(lyrics_transcriber, "_get_model", lambda: FakeModel())

    lines = lyrics_transcriber.transcribe_lyrics("vocals.wav")

    assert len(lines) == 2
    assert lines[0].start == 0.0 and lines[0].end == 2.0 and lines[0].text == "primeira linha"
    assert lines[1].text == "segunda linha"


def test_habilitado_sem_segmentos_devolve_lista_vazia(monkeypatch):
    monkeypatch.setenv("LYRICS_ENABLED", "true")
    get_settings.cache_clear()

    class FakeModel:
        def transcribe(self, path, word_timestamps=False):
            return [], {}

    monkeypatch.setattr(lyrics_transcriber, "_get_model", lambda: FakeModel())
    assert lyrics_transcriber.transcribe_lyrics("vocals.wav") == []
