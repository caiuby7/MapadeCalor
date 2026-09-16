"""Servidor FastAPI — API multi-fonte de mapa de calor de sentimentos."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analyzer import analyze_items, build_summary
from collector import AVAILABLE_SOURCES, collect_all

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mapa de Calor — Sentimentos Multi-Fonte",
    description="Coleta menções do YouTube, Bluesky, Reddit e RSS; analisa sentimento e geolocalização.",
    version="2.0.0",
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
        "sources": {
            "youtube": bool(os.getenv("YOUTUBE_API_KEY")),
            "bluesky": True,  # API pública; credenciais opcionais
            "reddit": bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")),
            "news": True,  # RSS público, sem chave
        },
        "llm": {
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "huggingface": bool(os.getenv("HUGGINGFACE_API_KEY")),
            "fallback": "rule_based",
        },
    }


@app.get("/api/sources")
def list_sources():
    return {
        "sources": [
            {"id": "youtube", "label": "YouTube", "requires_key": True},
            {"id": "bluesky", "label": "Bluesky", "requires_key": False},
            {"id": "reddit", "label": "Reddit", "requires_key": True},
            {"id": "news", "label": "Notícias (RSS)", "requires_key": False},
        ]
    }


@app.get("/api/heatmap-data")
async def get_heatmap_data(
    query: str = Query(..., min_length=1, description="Palavra-chave de busca"),
    sources: str = Query(
        "youtube,bluesky,reddit,news",
        description="Fontes separadas por vírgula",
    ),
    max_videos: int = Query(5, ge=1, le=10),
    max_comments: int = Query(15, ge=1, le=50),
):
    """
    Coleta menções de múltiplas fontes em paralelo, analisa sentimento
    e retorna pontos + resumo com percentuais.
    """
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    invalid = [s for s in source_list if s not in AVAILABLE_SOURCES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Fontes inválidas: {invalid}. Disponíveis: {list(AVAILABLE_SOURCES)}",
        )

    items = await collect_all(
        query=query,
        sources=source_list,
        max_videos=max_videos,
        max_comments=max_comments,
    )

    if not items:
        return {"points": [], "summary": build_summary([])}

    points = await analyze_items(items)
    summary = build_summary(points)

    return {"points": points, "summary": summary}


@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend não encontrado")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
