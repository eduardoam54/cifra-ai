"""
Cache de análises no Supabase, por `video_id` (Fase 2).

Usa a REST API do PostgREST diretamente (via httpx) em vez do SDK
`supabase-py`, pra não somar mais uma dependência pesada por uma tabela só.

Se `SUPABASE_URL`/`SUPABASE_KEY` não estiverem configurados (`.env` vazio,
como hoje), todas as funções aqui são no-op — o pipeline se comporta
exatamente como na Fase 0/1, sempre reprocessando.
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.models import AnalysisResponse

logger = logging.getLogger(__name__)

_TABLE = "analyses"


def _rest_config() -> Optional[tuple[str, dict]]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        return None
    base_url = f"{settings.supabase_url.rstrip('/')}/rest/v1/{_TABLE}"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
    }
    return base_url, headers


def get_cached_analysis(video_id: Optional[str]) -> Optional[AnalysisResponse]:
    """Consulta o cache; retorna None em cache miss ou se o cache estiver desabilitado."""
    config = _rest_config()
    if not config or not video_id:
        return None
    base_url, headers = config

    try:
        resp = httpx.get(
            base_url,
            headers=headers,
            params={"video_id": f"eq.{video_id}", "select": "*", "limit": 1},
            timeout=5.0,
        )
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        logger.warning("Falha ao consultar cache Supabase (video_id=%s)", video_id, exc_info=True)
        return None

    if not rows:
        return None

    row = rows[0]
    settings = get_settings()
    if row.get("model_version") != settings.model_version:
        # Cache de uma versão antiga do modelo — reprocessa em vez de servir resultado obsoleto.
        return None

    return AnalysisResponse(
        video_id=row["video_id"],
        bpm=row["bpm"],
        key=row["key"],
        chords_timeline=row["chords_timeline"],
        model_version=row["model_version"],
        processing_time_s=0.0,
        cached=True,
    )


def save_analysis(result: AnalysisResponse) -> None:
    """Salva o resultado no cache; no-op se o cache estiver desabilitado ou sem video_id."""
    config = _rest_config()
    if not config or not result.video_id:
        return
    base_url, headers = config

    payload = {
        "video_id": result.video_id,
        "chords_timeline": [c.model_dump() for c in result.chords_timeline],
        "bpm": result.bpm,
        "key": result.key,
        "model_version": result.model_version,
    }
    try:
        resp = httpx.post(
            base_url,
            headers={**headers, "Prefer": "resolution=merge-duplicates"},
            json=payload,
            timeout=5.0,
        )
        resp.raise_for_status()
    except Exception:
        logger.warning("Falha ao salvar cache Supabase (video_id=%s)", result.video_id, exc_info=True)
