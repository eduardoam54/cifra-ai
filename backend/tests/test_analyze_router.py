"""
Testes do router /analyze focados na ramificação do modo rápido (backlog
9.2): confirma que separate_stems (Demucs) só é chamado quando o recognizer
ativo precisa de stems separados (NEEDS_SEPARATION=True), e é pulado quando
não precisa. Todos os serviços pesados são substituídos por fakes via
monkeypatch — não roda Demucs/librosa de verdade.
"""

import io

import pytest
from fastapi.testclient import TestClient

import app.routers.analyze as analyze_module
from app.config import get_settings
from app.main import app
from app.models import ChordEvent


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _dummy_upload():
    return {"audio_file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")}


def test_modo_padrao_chama_separacao_demucs(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    get_settings.cache_clear()

    called = {}

    def fake_separate_stems(audio_path, stems_dir):
        called["separate_stems"] = True
        return {"bass": audio_path, "vocals": audio_path, "other": audio_path, "drums": audio_path}

    class FakeRecognizer:
        NEEDS_SEPARATION = True

        def recognize(self, stems):
            assert "bass" in stems
            return [ChordEvent(start=0.0, end=1.0, chord="C")]

    monkeypatch.setattr(analyze_module, "separate_stems", fake_separate_stems)
    monkeypatch.setattr(analyze_module, "detect_bpm", lambda p: 120.0)
    monkeypatch.setattr(analyze_module, "detect_key", lambda p: "C maior")
    monkeypatch.setattr(analyze_module, "transcribe_lyrics", lambda p: [])
    monkeypatch.setattr(analyze_module, "get_chord_recognizer", lambda: FakeRecognizer())

    with TestClient(app) as client:
        resp = client.post("/analyze", files=_dummy_upload(), data={"video_id": "v1"})

    assert resp.status_code == 200
    assert called.get("separate_stems") is True
    assert resp.json()["chords_timeline"][0]["chord"] == "C"


def test_modo_rapido_pula_separacao_demucs(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    get_settings.cache_clear()

    def _boom(*args, **kwargs):
        raise AssertionError("não deveria chamar separate_stems no modo rápido")

    class FakeFastRecognizer:
        NEEDS_SEPARATION = False

        def recognize(self, stems):
            assert set(stems.keys()) == {"mix"}
            return [ChordEvent(start=0.0, end=1.0, chord="G")]

    monkeypatch.setattr(analyze_module, "separate_stems", _boom)
    monkeypatch.setattr(analyze_module, "detect_bpm", lambda p: 120.0)
    monkeypatch.setattr(analyze_module, "detect_key", lambda p: "C maior")
    monkeypatch.setattr(analyze_module, "transcribe_lyrics", lambda p: [])
    monkeypatch.setattr(analyze_module, "get_chord_recognizer", lambda: FakeFastRecognizer())

    with TestClient(app) as client:
        resp = client.post("/analyze", files=_dummy_upload(), data={"video_id": "v2"})

    assert resp.status_code == 200
    assert resp.json()["chords_timeline"][0]["chord"] == "G"


def test_modo_rapido_usa_mixagem_completa_pra_letra(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    get_settings.cache_clear()

    lyrics_calls = []

    class FakeFastRecognizer:
        NEEDS_SEPARATION = False

        def recognize(self, stems):
            return []

    monkeypatch.setattr(analyze_module, "separate_stems",
                         lambda *a, **k: (_ for _ in ()).throw(AssertionError("nao deveria separar")))
    monkeypatch.setattr(analyze_module, "detect_bpm", lambda p: 120.0)
    monkeypatch.setattr(analyze_module, "detect_key", lambda p: "C maior")
    monkeypatch.setattr(analyze_module, "get_chord_recognizer", lambda: FakeFastRecognizer())
    monkeypatch.setattr(analyze_module, "transcribe_lyrics", lambda p: lyrics_calls.append(p) or [])

    with TestClient(app) as client:
        resp = client.post("/analyze", files=_dummy_upload(), data={"video_id": "v3"})

    assert resp.status_code == 200
    # Sem stem de vocais isolado, a transcricao usa a mixagem completa (audio_path).
    assert len(lyrics_calls) == 1
    assert lyrics_calls[0].endswith("input.wav")
