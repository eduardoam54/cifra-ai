"""
Testes do cache Supabase (app/services/cache.py) — sem depender de um
projeto Supabase real: httpx.get/post são substituídos por fakes via
monkeypatch, e o transporte de rede nunca é tocado.
"""

import httpx
import pytest

from app.config import get_settings
from app.models import AnalysisResponse, ChordEvent
from app.services import cache


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sample_result(video_id="abc123") -> AnalysisResponse:
    return AnalysisResponse(
        video_id=video_id,
        bpm=120.0,
        key="C maior",
        chords_timeline=[ChordEvent(start=0.0, end=1.0, chord="C")],
        model_version="0.1.0",
        processing_time_s=1.0,
    )


def test_no_op_without_supabase_credentials(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    get_settings.cache_clear()

    assert cache.get_cached_analysis("abc123") is None

    def _boom(*args, **kwargs):
        raise AssertionError("não deveria fazer requisição HTTP sem credenciais configuradas")

    monkeypatch.setattr(cache.httpx, "get", _boom)
    monkeypatch.setattr(cache.httpx, "post", _boom)

    cache.save_analysis(_sample_result())  # não deve levantar nem chamar HTTP


def test_cache_hit_returns_cached_analysis(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    row = {
        "video_id": "abc123",
        "bpm": 120.0,
        "key": "C maior",
        "chords_timeline": [{"start": 0.0, "end": 2.0, "chord": "C", "confidence": 0.9}],
        "model_version": get_settings().model_version,
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        assert params["video_id"] == "eq.abc123"
        return httpx.Response(200, json=[row], request=httpx.Request("GET", url))

    monkeypatch.setattr(cache.httpx, "get", fake_get)

    result = cache.get_cached_analysis("abc123")
    assert result is not None
    assert result.cached is True
    assert result.bpm == 120.0
    assert result.chords_timeline[0].chord == "C"


def test_cache_miss_returns_none(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    def fake_get(url, headers=None, params=None, timeout=None):
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setattr(cache.httpx, "get", fake_get)
    assert cache.get_cached_analysis("video-sem-cache") is None


def test_cache_ignores_stale_model_version(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    row = {
        "video_id": "abc123",
        "bpm": 120.0,
        "key": "C maior",
        "chords_timeline": [],
        "model_version": "0.0.1-old",
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        return httpx.Response(200, json=[row], request=httpx.Request("GET", url))

    monkeypatch.setattr(cache.httpx, "get", fake_get)
    assert cache.get_cached_analysis("abc123") is None


def test_get_cached_analysis_survives_http_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    def fake_get(url, headers=None, params=None, timeout=None):
        raise httpx.ConnectError("falha de rede simulada")

    monkeypatch.setattr(cache.httpx, "get", fake_get)
    assert cache.get_cached_analysis("abc123") is None


def test_save_analysis_posts_expected_payload(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(cache.httpx, "post", fake_post)

    cache.save_analysis(_sample_result())

    assert captured["json"]["video_id"] == "abc123"
    assert captured["json"]["chords_timeline"] == [
        {"start": 0.0, "end": 1.0, "chord": "C", "confidence": None}
    ]
    assert captured["headers"]["Prefer"] == "resolution=merge-duplicates"


def test_save_analysis_without_video_id_is_noop(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    get_settings.cache_clear()

    def _boom(*args, **kwargs):
        raise AssertionError("não deveria salvar cache sem video_id")

    monkeypatch.setattr(cache.httpx, "post", _boom)
    cache.save_analysis(_sample_result(video_id=None))
