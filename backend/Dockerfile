# Cifras AI — Backend (Fase 0)
# Build: docker build -t cifras-ai-backend .
# Run:   docker run -p 8000:8000 --env-file .env cifras-ai-backend

FROM python:3.11-slim

# ffmpeg é necessário para librosa + demucs decodificarem mp3/m4a
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-baixa o modelo Demucs para não baixar em cada cold start
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')"

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
