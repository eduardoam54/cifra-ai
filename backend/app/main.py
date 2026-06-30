import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyze

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    logging.getLogger(__name__).info(
        "%s v%s iniciado — backend de acordes: %s",
        settings.app_name, settings.model_version, settings.chord_backend,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.model_version,
    description=(
        "Backend de IA para reconhecimento de acordes, BPM e tonalidade. "
        "Parte do projeto Cifras AI (Fase 0 — PoC)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restringir na Fase 2 após definir origem da extensão
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(analyze.router)


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "version": settings.model_version}
