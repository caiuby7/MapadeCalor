"""Orquestrador de coleta — Bluesky + YouTube em paralelo."""

import asyncio
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from collectors.bluesky import collect_bluesky
from collectors.youtube import collect_youtube

logger = logging.getLogger(__name__)

SourceType = Literal["youtube", "bluesky"]
AVAILABLE_SOURCES: tuple[SourceType, ...] = ("youtube", "bluesky")


class MentionItem(BaseModel):
    """Schema unificado de menção coletada."""

    source: SourceType
    text: str
    author: str = ""
    created_at: str = ""
    source_url: str = ""


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
    """Coleta menções de todas as fontes selecionadas via asyncio.gather."""
    active: list[SourceType] = [
        s for s in (sources or list(AVAILABLE_SOURCES)) if s in AVAILABLE_SOURCES
    ]

    if not active:
        return []

    tasks = []
    for source in active:
        if source == "youtube":
            tasks.append(_safe_collect(source, collect_youtube(query, max_videos, max_comments)))
        else:
            tasks.append(_safe_collect(source, collect_bluesky(query)))

    results = await asyncio.gather(*tasks)

    items: list[dict[str, Any]] = []
    for source, batch in zip(active, results):
        logger.info("Fonte %s: %d menções", source, len(batch))
        items.extend(batch)

    logger.info("Total: %d menções para '%s'", len(items), query)
    return items
