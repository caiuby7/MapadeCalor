"""API FastAPI do mapa de sentimentos."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.analyzer import SentimentAnalyzer
from backend.collector import YouTubeCollector, YouTubeCollectorError


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
load_dotenv(BASE_DIR / ".env")

MAX_VIDEOS = int(os.getenv("MAX_VIDEOS", "5"))
MAX_COMMENTS = int(os.getenv("MAX_COMMENTS", "100"))
ANALYSIS_CONCURRENCY = int(os.getenv("ANALYSIS_CONCURRENCY", "5"))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes"}

app = FastAPI(
    title="Mapa de Sentimentos",
    description="Comentários públicos do YouTube analisados por sentimento e região.",
    version="1.0.0",
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    intensity: float
    sentiment: str
    sentiment_score: float
    location: str
    text: str


DEMO_COMMENTS = [
    "Excelente iniciativa, parabéns! Acompanhando de São Paulo.",
    "Que absurdo, isso é uma vergonha aqui no Rio de Janeiro.",
    "Estou vendo as notícias de Recife e ainda estou avaliando.",
    "Gostei muito da proposta. Um abraço de Curitiba!",
    "Péssimo, só mentira. Falando de Salvador.",
    "Acompanhando de Manaus, não tenho opinião formada.",
]


def get_analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "youtube_configured": bool(os.getenv("YOUTUBE_API_KEY")),
        "llm_configured": bool(os.getenv("OPENAI_API_KEY")),
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/heatmap-data", response_model=list[HeatmapPoint])
async def heatmap_data(
    query: str = Query(..., min_length=2, max_length=120),
) -> list[HeatmapPoint]:
    """Coleta comentários e os analisa em paralelo, com concorrência limitada."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key and not DEMO_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "YOUTUBE_API_KEY não configurada. Configure a chave ou habilite "
                "DEMO_MODE=true para testar sem consumir APIs externas."
            ),
        )

    if DEMO_MODE and not api_key:
        texts = DEMO_COMMENTS
    else:
        try:
            collector = YouTubeCollector(api_key)
            comments = await run_in_threadpool(
                collector.collect, query, MAX_VIDEOS, MAX_COMMENTS
            )
            texts = [comment.text for comment in comments]
        except YouTubeCollectorError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    analyzer = get_analyzer()
    semaphore = asyncio.Semaphore(max(1, ANALYSIS_CONCURRENCY))

    async def analyze_one(text: str) -> HeatmapPoint:
        async with semaphore:
            result = await analyzer.analyze(text)
        return HeatmapPoint(
            lat=result.lat,
            lng=result.lng,
            intensity=max(0.15, abs(result.sentiment_score)),
            sentiment=result.sentiment_label,
            sentiment_score=result.sentiment_score,
            location=result.detected_location,
            text=text,
        )

    return list(await asyncio.gather(*(analyze_one(text) for text in texts)))


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend não encontrado.")
    return FileResponse(index)
