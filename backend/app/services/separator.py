"""
Separação de fontes com Demucs.

Retorna um dict com caminhos para cada stem separado:
  {"bass": "/tmp/.../bass.wav", "drums": "...", "vocals": "...", "other": "..."}

O stem de bateria é descartado pelo pipeline de acordes, mas é gerado
mesmo assim porque o Demucs separa em lote e não tem modo "skip stem".
"""

import subprocess
import sys
import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def separate_stems(audio_path: str, output_dir: str) -> dict[str, str]:
    """
    Roda Demucs sobre `audio_path` e devolve os caminhos dos stems.

    Demucs escreve em: <output_dir>/<model>/<nome_do_arquivo>/{bass,drums,vocals,other}.wav
    """
    settings = get_settings()
    audio = Path(audio_path)
    out = Path(output_dir)
    bootstrap = Path(__file__).with_name("_demucs_bootstrap.py")

    cmd = [
        sys.executable, str(bootstrap),
        "--name", settings.demucs_model,
        "--out", str(out),
        "--device", settings.demucs_device,
        "-j", str(settings.demucs_jobs),
        str(audio),
    ]

    logger.info("Rodando Demucs: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Demucs falhou:\n{result.stderr}")

    stem_dir = out / settings.demucs_model / audio.stem
    stems = {}
    for stem in ("bass", "drums", "vocals", "other"):
        p = stem_dir / f"{stem}.wav"
        if not p.exists():
            raise FileNotFoundError(f"Stem esperado não encontrado: {p}")
        stems[stem] = str(p)

    logger.info("Stems gerados em %s", stem_dir)
    return stems
