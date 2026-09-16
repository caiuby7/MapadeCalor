"""Servidor FastAPI — API de heatmap de sentimentos a partir de comentários do YouTube."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analyzer import analyze_comments
from collector import (
    YouTubeCollectorError,
    collect_comments,
    generate_demo_comments,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mapa de Calor de Sentimentos",
    description="Coleta comentários do YouTube, analisa sentimento e geolocaliza para heatmap.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    intensity: float = Field(ge=0, le=1)
    sentiment: str
    sentiment_score: float | None = None
    text: str
    author: str | None = None
    location: str | None = None
    video_title: str | None = None


class HeatmapResponse(BaseModel):
    query: str
    source: str
    total: int
    points: list[HeatmapPoint]
    summary: dict[str, int]


def _demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def _has_youtube_key() -> bool:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    return bool(key) and not key.startswith("sua_chave")


def _has_openai_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key) and not key.startswith("sua_chave")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "youtube_configured": _has_youtube_key(),
        "openai_configured": _has_openai_key(),
        "demo_mode": _demo_mode_enabled(),
    }


@app.get("/api/heatmap-data", response_model=HeatmapResponse)
def heatmap_data(
    query: str = Query(..., min_length=1, max_length=120, description="Palavra-chave de busca"),
    demo: bool | None = Query(
        None,
        description="Força modo demo. Se omitido, usa DEMO_MODE / disponibilidade das chaves.",
    ),
):
    """
    Dispara a busca no YouTube, processa sentimento e retorna pontos para o mapa de calor.
    """
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Parâmetro query é obrigatório.")

    force_demo = demo if demo is not None else False
    use_demo = force_demo or (not _has_youtube_key() and _demo_mode_enabled())

    source = "youtube"
    try:
        if use_demo:
            comments = generate_demo_comments(query)
            source = "demo"
        else:
            comments = collect_comments(query)
            if not comments and _demo_mode_enabled():
                logger.info("Sem comentários no YouTube; caindo para demo.")
                comments = generate_demo_comments(query)
                source = "demo-fallback"
    except YouTubeCollectorError as exc:
        if _demo_mode_enabled():
            logger.warning("YouTube indisponível (%s). Usando demo.", exc)
            comments = generate_demo_comments(query)
            source = "demo-fallback"
        else:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro na coleta")
        raise HTTPException(status_code=500, detail=f"Erro na coleta: {exc}") from exc

    if not comments:
        return HeatmapResponse(
            query=query,
            source=source,
            total=0,
            points=[],
            summary={"positivo": 0, "neutro": 0, "negativo": 0},
        )

    # Em modo demo (ou sem OpenAI), usa heurística; com chave, tenta LLM.
    use_llm = _has_openai_key() and source == "youtube"
    try:
        points = analyze_comments(comments, use_llm=use_llm)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro na análise")
        raise HTTPException(status_code=500, detail=f"Erro na análise: {exc}") from exc

    summary = {"positivo": 0, "neutro": 0, "negativo": 0}
    for point in points:
        key = point.get("sentiment", "neutro")
        if key not in summary:
            key = "neutro"
        summary[key] += 1

    return HeatmapResponse(
        query=query,
        source=source,
        total=len(points),
        points=[HeatmapPoint(**p) for p in points],
        summary=summary,
    )


# Serve o frontend buildado (se existir) ou o index.html estático.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_STATIC = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def serve_spa():
        return FileResponse(FRONTEND_DIST / "index.html")

elif (FRONTEND_STATIC / "index.html").is_file():

    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_STATIC / "index.html")
