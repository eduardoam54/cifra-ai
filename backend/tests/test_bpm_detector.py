"""
Testes de app/services/bpm_detector.py — usam um click track sintético
gerado em memória (sem depender de arquivo de áudio real) e um sinal fraco
(sem percussão), gravados em .wav temporário via soundfile.

Cobrem a regressão corrigida: BPM = 0.0 em áudio com onset fraco/pouca
percussão (era o comportamento de librosa.beat.beat_track nesse caso).
"""

import numpy as np
import soundfile as sf

from app.services.bpm_detector import detect_bpm

SR = 22050


def _write_wav(tmp_path, name, y, sr=SR):
    path = tmp_path / name
    sf.write(str(path), y, sr)
    return str(path)


def _click_track(bpm: float, duration_s: float = 8.0, sr: int = SR) -> np.ndarray:
    interval = 60.0 / bpm
    n = int(duration_s * sr)
    y = np.zeros(n)

    click_len = int(0.02 * sr)
    t = np.arange(click_len) / sr
    click = np.sin(2 * np.pi * 1000 * t) * np.exp(-30 * t)

    for beat_time in np.arange(0, duration_s, interval):
        start = int(beat_time * sr)
        end = min(start + click_len, n)
        y[start:end] += click[: end - start]

    return y


def test_detecta_bpm_proximo_do_real_em_click_track(tmp_path):
    y = _click_track(bpm=120.0)
    path = _write_wav(tmp_path, "click_120.wav", y)

    bpm = detect_bpm(path)

    assert 110.0 <= bpm <= 130.0  # tolerância pra imprecisão do estimador


def test_nao_retorna_zero_em_audio_sem_percussao(tmp_path):
    # Tom puro sustentado — sem onsets rítmicos, é o caso que antes dava BPM=0.0
    # com librosa.beat.beat_track.
    t = np.arange(int(5.0 * SR)) / SR
    y = 0.5 * np.sin(2 * np.pi * 440 * t)
    path = _write_wav(tmp_path, "tom_puro.wav", y)

    bpm = detect_bpm(path)

    assert bpm > 0.0
