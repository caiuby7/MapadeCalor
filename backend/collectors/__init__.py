"""Orquestrador de coleta — todas as APIs gratuitas em paralelo."""

import asyncio
import logging
from typing import Any, Literal

from pydantic import BaseModel

from collectors.bluesky import collect_bluesky
from collectors.news import collect_news
from collectors.reddit import collect_reddit
from collectors.youtube import collect_youtube

logger = logging.getLogger(__name__)

SourceType = Literal["youtube", "bluesky", "reddit", "news"]
AVAILABLE_SOURCES: tuple[SourceType, ...] = ("youtube", "bluesky", "reddit", "news")

SOURCE_META = {
    "youtube": {"label": "YouTube", "requires_key": True, "free_tier": True},
    "bluesky": {"label": "Bluesky", "requires_key": False, "free_tier": True},
    "reddit": {"label": "Reddit", "requires_key": True, "free_tier": True},
    "news": {"label": "Notícias RSS", "requires_key": False, "free_tier": True},
}


class MentionItem(BaseModel):
    """Schema unificado de menção coletada."""

    source: SourceType
    text: str
    author: str = ""
    created_at: str = ""
    source_url: str = ""
    source_label: str = ""


async def _safe_collect(name: str, coro) -> list[dict[str, Any]]:
    try:
        return await coro
    except Exception as exc:
        logger.error("Coletor %s falhou: %s", name, exc)
        return []


async def collect_all(
    query: str,
    sources: list[str] | None = None,
    max_videos: int = 5,
    max_comments: int = 20,
) -> list[dict[str, Any]]:
    """Coleta menções de todas as fontes gratuitas selecionadas via asyncio.gather."""
    active: list[SourceType] = [
        s for s in (sources or list(AVAILABLE_SOURCES)) if s in AVAILABLE_SOURCES
    ]

    if not active:
        return []

    def _build_task(source: SourceType):
        if source == "youtube":
            return collect_youtube(query, max_videos, max_comments)
        if source == "bluesky":
            return collect_bluesky(query)
        if source == "reddit":
            return collect_reddit(query)
        return collect_news(query)

    tasks = [_safe_collect(src, _build_task(src)) for src in active]
    results = await asyncio.gather(*tasks)

    items: list[dict[str, Any]] = []
    for source, batch in zip(active, results):
        logger.info("Fonte %s: %d menções", source, len(batch))
        items.extend(batch)

    logger.info("Total: %d menções de %d fontes para '%s'", len(items), len(active), query)
    return items
