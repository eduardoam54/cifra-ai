from pydantic import BaseModel, Field
from typing import Optional
import uuid


class ChordEvent(BaseModel):
    start: float = Field(..., description="Início do acorde em segundos")
    end: float = Field(..., description="Fim do acorde em segundos")
    chord: str = Field(..., description="Símbolo do acorde (ex.: Am7, C#maj7, G/B)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class LyricLine(BaseModel):
    start: float = Field(..., description="Início da linha em segundos")
    end: float = Field(..., description="Fim da linha em segundos")
    text: str = Field(..., description="Texto transcrito da linha")


class AnalysisRequest(BaseModel):
    video_id: Optional[str] = Field(
        None,
        description="ID do YouTube ou hash do áudio — usado como chave de cache",
    )


class AnalysisResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: Optional[str] = None
    bpm: float = Field(..., description="Andamento detectado em BPM")
    key: str = Field(..., description="Tonalidade detectada (ex.: 'A maior', 'D# menor')")
    chords_timeline: list[ChordEvent]
    model_version: str = Field(..., description="Versão do modelo ACR que gerou o resultado")
    processing_time_s: float = Field(..., description="Tempo de processamento em segundos")
    cached: bool = Field(False, description="True se o resultado veio do cache (Supabase) em vez de reprocessar")
    lyrics: list[LyricLine] = Field(
        default_factory=list,
        description=(
            "Letra transcrita por linha (backlog 9.1, opt-in via LYRICS_ENABLED). "
            "Nunca persistida no cache Supabase — risco de copyright maior que "
            "acordes/BPM/tom, ver seção 7.1/9.1 do plano."
        ),
    )


class ErrorResponse(BaseModel):
    detail: str
    request_id: Optional[str] = None
