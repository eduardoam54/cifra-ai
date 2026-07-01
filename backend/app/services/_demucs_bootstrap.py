"""
Bootstrap usado para rodar o Demucs em subprocess (ver `separator.py`).

Desde o Python 3.8, `ctypes.CDLL` no Windows não resolve mais dependências
de DLL via `PATH` — só via `os.add_dll_directory()`. Sem isso, o torchcodec
(usado pelo torchaudio para salvar os stems) falha ao carregar as DLLs do
FFmpeg mesmo com o FFmpeg compartilhado (`Gyan.FFmpeg.Shared`) corretamente
instalado e presente no PATH do processo.

Por isso o Demucs não é chamado direto via `-m demucs`: este script roda
antes, registra os diretórios do PATH que contêm as DLLs do FFmpeg via
`os.add_dll_directory()`, e só então invoca o Demucs.
"""

import os
import runpy


def _register_ffmpeg_dll_dirs() -> None:
    if not hasattr(os, "add_dll_directory"):
        return  # não-Windows: PATH normal já resolve

    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isdir(entry):
            continue
        try:
            has_ffmpeg_dlls = any(
                name.lower().startswith("avcodec-") for name in os.listdir(entry)
            )
        except OSError:
            continue
        if has_ffmpeg_dlls:
            os.add_dll_directory(entry)


if __name__ == "__main__":
    _register_ffmpeg_dll_dirs()
    runpy.run_module("demucs", run_name="__main__")
