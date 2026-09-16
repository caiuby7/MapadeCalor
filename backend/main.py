"""Servidor FastAPI — monitoramento de menções com mapa de calor por sentimento."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analyzer import analyze_items, build_summary
from collectors import AVAILABLE_SOURCES, SOURCE_META, collect_all
from config import get_config_status

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mapa de Calor — Menções na Web",
    description="Coleta menções de APIs gratuitas, classifica sentimento e plota no mapa.",
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
    cfg = get_config_status()
    return {
        "status": "ok",
        "sources": {
            "youtube": {"configured": cfg["youtube"], **SOURCE_META["youtube"]},
            "bluesky": {"configured": True, **SOURCE_META["bluesky"]},
            "reddit": {"configured": cfg["reddit"], **SOURCE_META["reddit"]},
            "news": {"configured": True, **SOURCE_META["news"]},
        },
        "llm": {
            "groq": cfg["groq"],
            "openai": cfg["openai"],
            "fallback": "rule_based",
        },
    }


@app.get("/api/sources")
def list_sources():
    return {
        "sources": [
            {"id": src, **meta}
            for src, meta in SOURCE_META.items()
        ]
    }


SETUP_TIPS = [
    {
        "id": "groq",
        "title": "Groq — Sentimento via LLM",
        "configured": lambda: get_config_status()["groq"],
        "required": False,
        "recommended": True,
        "env_vars": ["GROQ_API_KEY", "GROQ_MODEL"],
        "url": "https://console.groq.com/keys",
        "steps": [
            "Crie conta gratuita em console.groq.com",
            "API Keys → Create API Key",
            "Cole GROQ_API_KEY no arquivo backend/.env",
        ],
    },
    {
        "id": "youtube",
        "title": "YouTube Data API v3",
        "configured": lambda: get_config_status()["youtube"],
        "required": False,
        "recommended": True,
        "env_vars": ["YOUTUBE_API_KEY"],
        "url": "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
        "steps": [
            "Google Cloud Console → criar projeto",
            "Ativar YouTube Data API v3",
            "Credenciais → Chave de API",
            "Cole YOUTUBE_API_KEY no backend/.env",
        ],
    },
    {
        "id": "reddit",
        "title": "Reddit API",
        "configured": lambda: get_config_status()["reddit"],
        "required": False,
        "recommended": False,
        "env_vars": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
        "url": "https://www.reddit.com/prefs/apps",
        "steps": [
            "reddit.com/prefs/apps → create app (tipo script)",
            "Copie client_id e secret",
            "Cole no backend/.env e reinicie o servidor",
        ],
    },
    {
        "id": "news",
        "title": "Notícias (Google News + RSS)",
        "configured": lambda: True,
        "required": False,
        "recommended": False,
        "env_vars": [],
        "url": None,
        "steps": ["Funciona automaticamente, sem chave."],
    },
    {
        "id": "bluesky",
        "title": "Bluesky",
        "configured": lambda: True,
        "required": False,
        "recommended": False,
        "env_vars": [],
        "url": None,
        "steps": ["API pública gratuita, sem chave necessária."],
    },
]


@app.get("/api/setup-guide")
def setup_guide():
    """Retorna dicas de configuração com status atual."""
    tips = []
    for tip in SETUP_TIPS:
        tips.append({
            "id": tip["id"],
            "title": tip["title"],
            "configured": tip["configured"](),
            "recommended": tip["recommended"],
            "env_vars": tip["env_vars"],
            "url": tip["url"],
            "steps": tip["steps"],
        })
    missing = [t for t in tips if not t["configured"] and t["env_vars"]]
    return {
        "tips": tips,
        "ready": len(missing) == 0,
        "missing_count": len(missing),
        "env_file": "backend/.env",
        "setup_doc": "/SETUP.md",
    }


@app.get("/api/heatmap-data")
async def get_heatmap_data(
    query: str = Query(..., min_length=1, description="Palavra-chave de busca"),
    sources: str = Query(
        "youtube,bluesky,reddit,news",
        description="Fontes: youtube,bluesky,reddit,news",
    ),
    max_videos: int = Query(5, ge=1, le=10),
    max_comments: int = Query(20, ge=1, le=50),
):
    """Coleta menções em paralelo de todas as APIs gratuitas, analisa e retorna pontos."""
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
        return {
            "points": [],
            "summary": build_summary([]),
            "collection": {"total_raw": 0, "by_source": {}, "message": "Nenhuma menção encontrada. Tente outro termo ou verifique as fontes."},
        }

    by_source_raw: dict[str, int] = {}
    for item in items:
        src = item.get("source", "unknown")
        by_source_raw[src] = by_source_raw.get(src, 0) + 1

    points = await analyze_items(items)
    return {
        "points": points,
        "summary": build_summary(points),
        "collection": {"total_raw": len(items), "by_source": by_source_raw},
    }


@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend não encontrado")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
