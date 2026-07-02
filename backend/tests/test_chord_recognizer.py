"""
Testes do reconhecedor de acordes por chroma (app/services/chord_recognizer.py).

Usam chroma sintético (vetores one-hot montados à mão) em vez de áudio real,
pra testar o template matching e o agrupamento de frames de forma
determinística e rápida.
"""

import numpy as np

from app.services import chord_recognizer as cr


def _one_hot_chroma(pitch_classes, n_frames=1):
    frame = np.zeros(12)
    frame[list(pitch_classes)] = 1.0
    return np.tile(frame[:, None], (1, n_frames))


def test_templates_cover_todas_qualidades_e_tonicas():
    n_expected = 12 * len(cr._QUALITIES)
    assert cr._TEMPLATES.shape == (n_expected, 12)
    assert len(cr._CHORD_NAMES) == n_expected
    assert "C" in cr._CHORD_NAMES        # maior
    assert "Am7" in cr._CHORD_NAMES      # menor com sétima
    assert "F#dim" in cr._CHORD_NAMES    # diminuto


def test_reconhece_triade_maior():
    chroma = _one_hot_chroma([0, 4, 7])  # C maior (C, E, G)
    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert len(events) == 1
    assert events[0].chord == "C"


def test_reconhece_menor_com_setima():
    chroma = _one_hot_chroma([9, 0, 4, 7])  # Am7 (A, C, E, G)
    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert events[0].chord == "Am7"


def test_reconhece_dominante_setima():
    chroma = _one_hot_chroma([7, 11, 2, 5])  # G7 (G, B, D, F)
    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert events[0].chord == "G7"


def test_reconhece_meio_diminuto():
    chroma = _one_hot_chroma([11, 2, 5, 9])  # Bm7b5 (B, D, F, A)
    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert events[0].chord == "Bm7b5"


def test_agrupa_frames_consecutivos_do_mesmo_acorde():
    chroma = _one_hot_chroma([0, 4, 7], n_frames=3)
    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert len(events) == 1
    assert events[0].start == 0.0
    assert events[0].end == 1.5


def test_separa_evento_quando_o_acorde_muda():
    c_major = np.zeros(12)
    c_major[[0, 4, 7]] = 1.0
    g_major = np.zeros(12)
    g_major[[7, 11, 2]] = 1.0
    chroma = np.stack([c_major, c_major, g_major], axis=1)

    events = cr._events_from_chroma(chroma, hop_s=0.5)
    assert [e.chord for e in events] == ["C", "G"]
    assert events[0].start == 0.0 and events[0].end == 1.0
    assert events[1].start == 1.0 and events[1].end == 1.5
