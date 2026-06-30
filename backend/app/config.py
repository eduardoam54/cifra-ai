from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    model_config = {"protected_namespaces": ("settings_",), "env_file": ".env", "env_file_encoding": "utf-8"}

    # Backend
    app_name: str = "Cifras AI Backend"
    model_version: str = "0.1.0"
    max_audio_duration_s: int = 600  # 10 min — limite de segurança
    upload_dir: str = "/tmp/cifras_uploads"

    # Demucs
    demucs_model: str = "htdemucs"          # ou "htdemucs_ft" para fine-tuned
    demucs_device: str = "cpu"              # "cuda" quando houver GPU
    demucs_jobs: int = 1

    # Chord recognizer
    # "chroma"  → fallback simples baseado em chroma (sem modelo externo)
    # "btc"     → BTC Chord Recognition (requer peso em CHORD_MODEL_PATH)
    chord_backend: str = "chroma"
    chord_model_path: str = ""

    # Supabase (Fase 2)
    supabase_url: str = ""
    supabase_key: str = ""



@lru_cache
def get_settings() -> Settings:
    return Settings()
