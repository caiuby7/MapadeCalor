"""Servidor FastAPI — API de mapa de calor de sentimentos."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analyzer import AnalyzerError, analyze_comments
from collector import YouTubeCollectorError, collect_comments_for_query

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mapa de Calor — Sentimentos YouTube",
    description="Coleta comentários do YouTube, analisa sentimento e geolocalização.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "youtube_configured": bool(os.getenv("YOUTUBE_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/api/heatmap-data")
def get_heatmap_data(
    query: str = Query(..., min_length=1, description="Palavra-chave para busca no YouTube"),
    max_videos: int = Query(5, ge=1, le=10),
    max_comments: int = Query(20, ge=1, le=50),
):
    """
    Coleta comentários do YouTube, analisa sentimento e retorna pontos para o mapa.
    """
    try:
        comments = collect_comments_for_query(
            query=query,
            max_videos=max_videos,
            max_comments_per_video=max_comments,
        )
    except YouTubeCollectorError as exc:
        logger.error("Erro na coleta: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not comments:
        return []

    use_fallback = not os.getenv("OPENAI_API_KEY")

    try:
        points = analyze_comments(comments, use_fallback=use_fallback)
    except AnalyzerError as exc:
        logger.error("Erro na análise: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return points


@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend não encontrado")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
